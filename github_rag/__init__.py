# -*- coding: utf-8 -*-
"""github-rag: GitHub kullanıcısının repolarını okuyup soruları yanıtlayan RAG.

Kullanım:
    from github_rag import GithubRag

    rag = GithubRag.from_github("kadiirgok")   # veya bir repo linki
    res = rag.ask("hangi dillerde yazılmış?")
    print(res["cevap"])   # res: {"cevap","kaynak","sure_saniye","dogrulandi"}
"""

import json
import re
import time
from collections import Counter
from pathlib import Path

from .answer import answer_from_collection, answer_from_web
from .config import Config, load_config
from .github import fetch_metadata, ingest_code, ingest_github, resolve_target
from .indexing import build_index, clear_collection, get_collection, reset_collection
from .llm import make_llm
from .prompts import CODE_PROMPT_TEMPLATE
from .retrieval import _kompakt, _source_anahtari

__version__ = "0.2.0"


def _sanitize(name: str) -> str:
    """Hedefi güvenli bir koleksiyon adına dönüştürür."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name) or "index"


# Kod detayı isteyen soruları işaretleyen anahtar kelimeler. Bu kelimeler geçerse
# README doğrulansa bile kod katmanına geçilir (kullanıcı implementasyon istiyor).
_CODE_KELIMELERI = {
    "kod", "code", "fonksiyon", "function", "def ", "class ", "dosya", "file",
    "implement", "method", "metod", "module", "modül", "import", "değişken",
    "variable", "endpoint", "algoritma", "algorithm", "mimari", "yapısı",
    "nasıl çalış", "nasil calis", "hangi dosyada", "nerede tanımlı",
}


def _is_code_sorusu(soru: str) -> bool:
    """Soru kod/implementasyon detayı istiyor mu?"""
    s = soru.lower()
    return any(k in s for k in _CODE_KELIMELERI)


class GithubRag:
    """Bir GitHub hedefini indeksleyip üzerinde soru-cevap yapan RAG aracı."""

    def __init__(self, target: str | None = None, config: Config | None = None):
        self.config = config or load_config()
        self.target = target
        self.owner = None
        self.collection = None
        self.collection_name = None
        self.bilinen_anahtarlar: list[str] = []
        self.repo_names: set[str] = set()
        self.repo_sayisi = 0
        self.repo_metadata: list[dict] = []
        self.son_repo: tuple[str, str] | None = None  # takip soruları için son odak repo
        self._llm = None
        self._code_coll_cache: dict[str, object] = {}

    @property
    def llm(self):
        if self._llm is None:
            self._llm = make_llm(self.config)
        return self._llm

    # --- İndeksleme (Katman 1: README) ---
    def _prepare_collection(self, target: str):
        parsed = resolve_target(target)
        self.owner = parsed["owner"]
        key = parsed["repo"] or parsed["owner"]
        self.collection_name = f"repos_{_sanitize(key)}"
        self.collection = get_collection(self.config.chroma_dir, self.collection_name)

    def index(self, target: str | None = None, force: bool = False) -> int:
        """Hedefin repo+README'lerini çekip indeksler; repo sayısını döndürür."""
        target = target or self.target
        if not target:
            raise ValueError("index() için bir GitHub hedefi gerekli.")
        self.target = target
        self._prepare_collection(target)

        if not force and self.collection.count() > 0:
            self._load_metadata()
            if not self.repo_metadata:
                self.repo_metadata = fetch_metadata(target, self.config.github_token)
                self._save_metadata()
            self._refresh_known_keys()
            print(f"'{target}' zaten indekslenmiş (cache). force=True ile yenilenebilir.")
            return self.repo_sayisi

        docs, metadata = ingest_github(target, self.config.github_token)
        if not docs:
            raise ValueError(f"'{target}' için okunabilir README bulunamadı.")

        # Force yeniden çekimde eski/öksüz chunk'ları temizle (build_index sadece upsert yapar).
        if force:
            clear_collection(self.config.chroma_dir, self.collection_name)

        self.repo_metadata = metadata
        self._save_metadata()
        build_index(docs, self.config.chroma_dir, self.collection_name,
                    self.config.embedding_model)
        self._refresh_known_keys()
        return self.repo_sayisi

    def detect_changes(self, target: str | None = None) -> dict:
        """Cache'li metadata'yı GitHub'daki güncel durumla karşılaştırır.

        Hafiftir: embedding/README çekmez, yalnızca repo listesini (`fetch_metadata`)
        getirir. Karşılaştırma: repo adı seti + `updated_at` + `stars`.
        """
        target = target or self.target
        if not target:
            raise ValueError("detect_changes için bir GitHub hedefi gerekli.")
        guncel = fetch_metadata(target, self.config.github_token)
        yeni = {m["name"]: m for m in guncel}
        eski = {m["name"]: m for m in (self.repo_metadata or [])}
        eklenen = sorted(set(yeni) - set(eski))
        kaldirilan = sorted(set(eski) - set(yeni))
        degisen = sorted(
            n for n in set(yeni) & set(eski)
            if yeni[n].get("updated_at") != eski[n].get("updated_at")
            or yeni[n].get("stars") != eski[n].get("stars")
        )
        return {"hedef": target, "eklenen": eklenen, "kaldirilan": kaldirilan,
                "degisen": degisen, "guncel": not (eklenen or kaldirilan or degisen)}

    def _refresh_known_keys(self):
        """Bilinen repo adlarını metadata + koleksiyon kaynaklarından toplar.

        Metadata tüm repoları bilir (README'siz/şablon README'li olanlar dahil);
        koleksiyon kaynakları ise yerel klasör modu gibi durumları kapsar. İkisinin
        birleşimi, odağı doğru bulmak için tam repo listesini verir.
        """
        try:
            names: set[str] = set()
            for m in self.repo_metadata:
                for key in ("name", "full_name"):
                    val = (m or {}).get(key, "")
                    if val:
                        names.add(val.split("/")[-1])
            metas = self.collection.get(include=["metadatas"]).get("metadatas", [])
            for m in metas:
                s = (m or {}).get("source", "")
                if s and s != "web":
                    names.add(s)
            self.repo_names = names
            self.repo_sayisi = len(names)
            self.bilinen_anahtarlar = [_kompakt(s) for s in names]
        except Exception:
            self.bilinen_anahtarlar = []
            self.repo_names = set()
            self.repo_sayisi = 0

    # --- Metadata kalıcılığı (cache sonrası da erişilebilir) ---
    def _meta_path(self) -> Path:
        return Path(self.config.chroma_dir) / f"{self.collection_name}_meta.json"

    def _save_metadata(self):
        try:
            self._meta_path().write_text(
                json.dumps(self.repo_metadata, ensure_ascii=False, indent=2),
                encoding="utf-8")
        except Exception:
            pass

    def _load_metadata(self):
        p = self._meta_path()
        if not p.is_file():
            self.repo_metadata = []
            return
        try:
            self.repo_metadata = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            self.repo_metadata = []

    # --- Kod okuma (Katman 2) ---
    def _find_focus(self, soru: str) -> tuple[str, str] | None:
        """Soruda adı geçen repoyu bulur; (owner, repo) döner, yoksa None."""
        if not self.owner:
            return None
        soru_kompakt = _kompakt(soru)
        en_iyi, en_iyi_uzunluk = None, 0
        for name in self.repo_names:
            key = _source_anahtari(name)
            if len(key) >= 4 and key in soru_kompakt and len(key) > en_iyi_uzunluk:
                en_iyi, en_iyi_uzunluk = name, len(key)
        return (self.owner, en_iyi) if en_iyi else None

    def read_code(self, owner: str, repo: str, force: bool = False):
        """Bir reponun kaynak kodunu çekip indeksler (koleksiyon döner, cache'li)."""
        collection_name = f"code_{_sanitize(owner)}_{_sanitize(repo)}"
        if collection_name in self._code_coll_cache:
            return self._code_coll_cache[collection_name]
        try:
            coll = get_collection(self.config.chroma_dir, collection_name)
            if not force and coll.count() > 0:
                self._code_coll_cache[collection_name] = coll
                return coll
        except Exception as exc:  # noqa: BLE001 — bozuk HNSW indeksi vb.
            print(f"Kod koleksiyonu bozuk ({collection_name}), yeniden oluşturuluyor: {exc}")
            coll = reset_collection(self.config.chroma_dir, collection_name)
        try:
            docs = ingest_code(owner, repo, self.config.github_token,
                               max_files=self.config.code_max_files,
                               max_size=self.config.code_max_size)
        except Exception as exc:  # noqa: BLE001 — kod okunamazsa sessizce atla
            print(f"Kod okunamadı ({owner}/{repo}): {exc}")
            self._code_coll_cache[collection_name] = coll
            return coll
        if docs:
            print(f"'{repo}' kodu okunuyor: {len(docs)} dosya...")
            # Force yeniden okumada eski chunk'ları temizle (upsert silmez).
            if force:
                clear_collection(self.config.chroma_dir, collection_name)
            # Kod küçük chunk'lara bölünür (token yoğunluğu yüksek -> bağlam taşmasını önler).
            build_index(docs, self.config.chroma_dir, collection_name,
                        self.config.embedding_model, chunk_size=150, overlap=20)
        self._code_coll_cache[collection_name] = coll
        return coll

    # --- Sorgulama (iki katmanlı) ---
    # Repo adı/açıklamasından ilgi alanı çıkarmak için basit anahtar kelime eşlemesi.
    _ALAN_ANAHTARLARI = {
        "veri bilimi / makine öğrenmesi": [
            "data-science", "data_science", "machine-learning", "ml", "churn",
            "telco", "deep-learning", "nlp", "dataset", "kaggle", "titanic", "veri",
        ],
        "mobil uygulama": ["flutter", "mobile", "dart", "android", "ios", "react-native"],
        "web / backend": ["web", "api", "backend", "frontend", "django", "flask",
                          "fastapi", "react", "vue", "node", "spring", ".net"],
        "sohbet / asistan / RAG": ["chat", "sohbet", "bot", "asistan", "rag", "llm", "cv"],
    }

    def _meta_cevap(self, soru: str) -> str | None:
        """İndeks + metadata'dan kesin cevaplanabilen soruları doğrudan yanıtlar.

        Bu sorular LLM'e/web'e gitmemeli: cevap zaten elimizdeki metadata'da.
        """
        s = soru.lower()
        # 1) Dil / ilgi alanı özeti (repo metadata'sından, deterministik)
        if any(k in s for k in ("alan", "dil", "diller", "ilgilen", "konu",
                                "neyi", "neyle", "neler yapmış", "neler yapmis")):
            return self._alan_ozeti()
        # 2) Repo sayısı / listesi
        if "proj" in s or "repo" in s:
            if "kaç" in s or "kac" in s:
                return f"Yüklenen GitHub hesabında {self.repo_sayisi} repo var."
            if any(k in s for k in ("hangi", "listele", "listesi", "neler")):
                return self._repo_listesi()
        return None

    def _repo_listesi(self) -> str:
        """Repo adları + dil + kısa açıklama içeren zengin liste döndürür."""
        if not self.repo_names:
            return "Henüz repo yüklenmedi."
        meta = {m.get("name"): m for m in self.repo_metadata}
        lines = [f"Bu hesapta {self.repo_sayisi} repo var:"]
        for name in sorted(self.repo_names):
            m = meta.get(name, {})
            parca = f"- {name}"
            if m.get("language"):
                parca += f" · {m['language']}"
            if m.get("description"):
                parca += f" — {m['description'][:80]}"
            lines.append(parca)
        return "\n".join(lines)

    def _alan_ozeti(self) -> str:
        """Metadata'dan dil dağılımı + ilgi alanı çıkarır (LLM'siz, kesin)."""
        if not self.repo_metadata:
            return "Henüz repo bilgisi yüklenmedi."
        diller = Counter(m.get("language") for m in self.repo_metadata if m.get("language"))
        alanlar = Counter()
        for m in self.repo_metadata:
            metin = f"{m.get('name', '')} {m.get('description', '')}".lower()
            for alan, kelimeler in self._ALAN_ANAHTARLARI.items():
                if any(k in metin for k in kelimeler):
                    alanlar[alan] += 1
        satirlar = [f"Toplam {self.repo_sayisi} repo."]
        if diller:
            satirlar.append("Kullanılan diller: " +
                            ", ".join(f"{d} ({n})" for d, n in diller.most_common()))
        if alanlar:
            satirlar.append("İlgi alanları: " +
                            ", ".join(f"{a} ({n} repo)" for a, n in alanlar.most_common()))
        return "\n".join(satirlar)

    def _repo_aciklama_cevabi(self, repo_name: str) -> str | None:
        """Belirli bir reponun metadata açıklamasını yapılandırılmış biçimde döndürür.

        README/kod içerik vermediğinde (örn. yalnızca notebook'tan oluşan repo),
        GitHub metadata'sındaki description/language/stars ile en azından ne olduğunu
        söyler; metadata da yoksa None döner (web fallback'e bırakır).
        """
        meta = None
        for m in self.repo_metadata:
            if m.get("name") == repo_name or (m.get("full_name") or "").split("/")[-1] == repo_name:
                meta = m
                break
        if not meta:
            return None

        satirlar = [f"**{meta.get('name', repo_name)}**"]
        if meta.get("description"):
            satirlar.append(f"- Açıklama: {meta['description'].strip()}")
        if meta.get("language"):
            satirlar.append(f"- Dil: {meta['language']}")
        satirlar.append(f"- Yıldız: {meta.get('stars', 0)}")
        if meta.get("html_url"):
            satirlar.append(f"- Bağlantı: {meta['html_url']}")
        return "\n".join(satirlar)

    def profile(self) -> dict:
        """Yapısal özet: /profile uç noktası ve arayüz için."""
        return {
            "repo_sayisi": self.repo_sayisi,
            "diller": {d: n for d, n in
                       Counter(m.get("language") for m in self.repo_metadata
                               if m.get("language")).most_common()},
            "toplam_yildiz": sum(m.get("stars", 0) for m in self.repo_metadata),
            "repolar": sorted(self.repo_metadata,
                              key=lambda m: -(m.get("stars", 0) or 0)),
        }

    def ask(self, soru: str) -> dict:
        """İki katmanlı RAG: önce README, yetmezse kod, en son web."""
        if self.collection is None or self.collection.count() == 0:
            return {"cevap": "Önce bir GitHub hesabı yükleyin (index()).",
                    "kaynak": "none", "sure_saniye": 0.0, "dogrulandi": False}

        # Soruda belirli bir repo adı geçiyor mu? (takip bağlamı değil, doğrudan sorudan)
        acik_focus = self._find_focus(soru)

        # Belirli bir repo adı yoksa, genel profil sorularını deterministik yanıtla
        # ("kaç repo var?", "hangi diller?" gibi). Repo adı geçiyorsa genel özete
        # atlamaz; soru o repoya dairdir, RAG'a gider.
        if acik_focus is None:
            meta = self._meta_cevap(soru)
            if meta is not None:
                return {"cevap": meta, "kaynak": "local", "sure_saniye": 0.0, "dogrulandi": True}

        # LLM anahtarı yoksa net bir yönlendirme döndür (uygulama yine de açılır).
        if not (self.config.deepseek_api_key or self.config.groq_api_key):
            return {"cevap": "Cevap üretmek için bir LLM anahtarı gerekli. `.env` dosyasına "
                             "DEEPSEEK_API_KEY (ve/veya GROQ_API_KEY) ekleyin. Repo sayısı, "
                             "dil dağılımı gibi özet sorular anahtarsız çalışır.",
                    "kaynak": "none", "sure_saniye": 0.0, "dogrulandi": False}

        t0 = time.time()
        cfg = self.config

        # Odak repo: sorudaki ad, yoksa önceki sorunun reposu (takip sorusu).
        focus = acik_focus or self.son_repo
        if focus is not None:
            self.son_repo = focus
        source_filter = focus[1] if focus else None

        # 1) README katmanı (odak varsa o repoya kapsüllenir)
        res = answer_from_collection(
            self.llm, soru, self.collection, self.bilinen_anahtarlar,
            cfg.embedding_model, top_k=cfg.top_k, max_tokens=cfg.max_tokens,
            esik=cfg.distance_threshold, source_filter=source_filter)
        # Doğrulanmış ve kod detayı istemeyen README cevabı -> direkt dön.
        if res is not None and res[2] and not _is_code_sorusu(soru):
            return self._yanit(res, t0)

        # 2) Kod katmanı (yalnızca odaklı repo varsa)
        if focus:
            code_coll = self.read_code(*focus)
            if code_coll.count() > 0:
                code_res = answer_from_collection(
                    self.llm, soru, code_coll, [], cfg.embedding_model,
                    top_k=cfg.code_top_k, max_tokens=cfg.max_tokens,
                    # Kod koleksiyonu zaten tek repoya (focus) kapsüllü olduğu için
                    # mesafe eşiği uygulanmaz (esik=2.0 cosine uzaklığının üst sınırı).
                    esik=2.0, majority_vote=False,
                    dogrula_sayisal=False, prompt_template=CODE_PROMPT_TEMPLATE)
                if code_res is not None:
                    return self._yanit(code_res, t0)

        # 3) README doğrulanamadıysa ama bir şey bulduysa onu döndür
        if res is not None:
            return self._yanit(res, t0)

        # 4) Repo adı biliniyor ama README/kod içerik vermediyse: metadata açıklamasına düş.
        if focus:
            meta_desc = self._repo_aciklama_cevabi(focus[1])
            if meta_desc is not None:
                return {"cevap": meta_desc, "kaynak": "local",
                        "sure_saniye": round(time.time() - t0, 3), "dogrulandi": True}

        # 5) Web fallback
        return self._yanit(
            answer_from_web(self.llm, soru, self.bilinen_anahtarlar, cfg.max_tokens), t0)

    def _yanit(self, res: tuple[str, str, bool], t0: float) -> dict:
        cevap, kaynak, dogrulandi = res
        return {"cevap": cevap, "kaynak": kaynak,
                "sure_saniye": round(time.time() - t0, 3), "dogrulandi": dogrulandi}

    # --- Fabrika yardımcıları ---
    @classmethod
    def from_github(cls, target: str, config: Config | None = None) -> "GithubRag":
        """Hedefi hemen indeksleyen kısayol."""
        rag = cls(target=target, config=config)
        rag.index()
        return rag

    @classmethod
    def from_local_folder(cls, folder_path: str, config: Config | None = None,
                          collection_name: str = "repos_local") -> "GithubRag":
        """Yerel .txt klasörünü (örnek veri / test) indeksleyen kısayol."""
        rag = cls(config=config)
        docs = []
        for txt in sorted(Path(folder_path).glob("*.txt")):
            content = txt.read_text(encoding="utf-8").strip()
            if content:
                docs.append({"text": content, "source": txt.name})
        if not docs:
            raise ValueError(f"'{folder_path}' içinde .txt dosyası bulunamadı.")
        rag.collection_name = collection_name
        rag.collection = get_collection(rag.config.chroma_dir, collection_name)
        build_index(docs, rag.config.chroma_dir, collection_name,
                    rag.config.embedding_model)
        rag._refresh_known_keys()
        return rag


__all__ = ["GithubRag", "Config", "load_config", "__version__"]
