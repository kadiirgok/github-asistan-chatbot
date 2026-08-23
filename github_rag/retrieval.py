# -*- coding: utf-8 -*-
"""Vektör arama + mesafe eşiği + repo-çoğunluk oyu + leksikal tie-break.

Kaynak (source) artık repo adıdır; eski "-proje.txt" dosya adı bağımlılığı
kaldırılmıştır. Çoğunluk oyu ve leksikal tie-break mantığı korunmuştur.
"""

import re
from collections import Counter

from .indexing import _get_embedding_model

# Leksikal tie-break'te elenen yaygın soru / fonksiyon kelimeleri (TR + EN).
_SORU_STOPWORDS = {
    # Türkçe soru kelimeleri
    "nedir", "nasıl", "hangi", "hangisi", "ne", "neden", "niye", "niçin",
    "kaç", "kim", "kime", "neyi", "nerede", "nereden", "nereye", "neresi",
    # Türkçe bağlaç / edat / sık fonksiyon kelimeleri
    "bir", "ve", "veya", "ya", "da", "de", "ile", "için", "daha", "çok", "en",
    "bu", "şu", "o", "gibi", "kadar", "göre", "sonra", "önce", "artık", "hâlâ",
    "mı", "mi", "mu", "mü", "ise", "çünkü", "ama", "fakat", "ancak", "olarak",
    "olan", "olduğu", "var", "yok", "her", "bazı", "tüm", "hiç",
    "verdi", "veriyor", "olur", "oldu", "eder", "etmek", "olmak",
    # İngilizce
    "what", "which", "how", "why", "when", "where", "who", "does", "do", "is",
    "are", "was", "were", "the", "and", "for", "with", "this", "that", "has",
    "have", "from", "into", "about", "used", "using", "use",
}


def _soru_kelimeleri(soru: str) -> list[str]:
    """Sorudaki anlamlı kelimeleri çıkarır (basit sezgisel yöntem)."""
    kelimeler = []
    for ham in soru.lower().split():
        t = ham.strip(".,;:!?()[]{}\"'")
        if len(t) >= 3 and t not in _SORU_STOPWORDS:
            kelimeler.append(t)
    return kelimeler


def _kompakt(metin: str) -> str:
    """Metni küçük harfe çevirip harf/rakam dışındaki karakterleri kaldırır."""
    return re.sub(r"[^a-z0-9çğıöşü]", "", metin.lower())


def _source_anahtari(source: str) -> str:
    """Kaynaktan kompakt anahtar üretir.

    Repo adı zaten temizdir; yalnızca olası ".txt" / "-proje" soneklerini
    (yerel klasör örnek verisi için) kırpar, sonra kompaktlar.
    """
    ad = source
    if ad.endswith(".txt"):
        ad = ad[:-4]
    if ad.endswith("-proje"):
        ad = ad[:-6]
    return _kompakt(ad)


def _mesafe_tie_break(adaylar: list[str], secilenler: list[tuple[str, str]]) -> str:
    """Beraberlikte en düşük mesafeli chunk'ın kaynağını seçer."""
    return min(adaylar, key=lambda s: next(i for i, (_, src) in enumerate(secilenler) if src == s))


def _lexikal_tie_break(adaylar: list[str], secilenler: list[tuple[str, str]],
                       soru: str) -> str:
    """Beraberlikteki kaynakları soru kelimeleriyle eşleştirir."""
    kelimeler = _soru_kelimeleri(soru)
    if not kelimeler:
        return _mesafe_tie_break(adaylar, secilenler)

    soru_kompakt = _kompakt(soru)

    skorlar = {}
    for source in adaylar:
        dosya = source.lower()
        metin = " ".join(doc for doc, s in secilenler if s == source).lower()
        skor = sum(1 for k in kelimeler if k in dosya or k in metin)
        anahtar = _source_anahtari(source)
        if anahtar and len(anahtar) >= 4 and anahtar in soru_kompakt:
            skor += 100
        skorlar[source] = skor

    en_iyi = max(adaylar, key=lambda s: skorlar[s])
    if skorlar[en_iyi] > 0:
        return en_iyi
    return _mesafe_tie_break(adaylar, secilenler)


def _leksikal_fallback(soru: str, collection) -> tuple[str, str]:
    """Embedding eşiği geçemediğinde, soruyu repo adlarıyla eşleştirir."""
    soru_kompakt = _kompakt(soru)
    if not soru_kompakt:
        return "", ""

    veri = collection.get(include=["documents", "metadatas"])
    docs = veri.get("documents", [])
    metas = veri.get("metadatas", [])

    by_source: dict[str, list[str]] = {}
    for doc, meta in zip(docs, metas):
        source = (meta or {}).get("source", "")
        if source == "web" or not source:
            continue
        by_source.setdefault(source, []).append(doc)

    en_iyi_source = ""
    en_iyi_uzunluk = 0
    for source in by_source:
        anahtar = _source_anahtari(source)
        if len(anahtar) >= 4 and anahtar in soru_kompakt and len(anahtar) > en_iyi_uzunluk:
            en_iyi_source = source
            en_iyi_uzunluk = len(anahtar)

    if not en_iyi_source:
        return "", ""
    return "\n\n".join(by_source[en_iyi_source]), en_iyi_source


def retrieve(soru: str, collection, embedding_model: str,
             top_k: int = 4, esik: float = 0.4, majority_vote: bool = True,
             source_filter: str | None = None) -> tuple[str, str]:
    """Soruyu embed eder, en yakın chunk'ları bulur ve (context, source) döndürür.

    Cosine mesafesi (1 - benzerlik) kullanılır; mesafesi eşiğin ÜSTÜNDE olan
    chunk'lar elenir. Kalan chunk'lar repo (source) bazında gruplanır ve çoğunluk
    oyuyla tek kaynak seçilir; beraberlikte leksikal tie-break uygulanır.
    """
    model = _get_embedding_model(embedding_model)

    query_embedding = model.encode([soru]).tolist()
    # source_filter verilmişse yalnızca o repoda ara (takip sorusu bağlamı için).
    where = {"source": source_filter} if source_filter else {"source": {"$ne": "web"}}
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        where=where,
    )

    retrieved_docs = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    secilenler = []
    for doc, dist, meta in zip(retrieved_docs, distances, metadatas):
        source = (meta or {}).get("source", "")
        if source == "web":
            continue
        # Kapsüllü aramada (source_filter) repo zaten belirlendi -> eşik uygulanmaz.
        if source_filter or dist <= esik:
            secilenler.append((doc, source))

    if not secilenler:
        # Kapsüllü arama boşsa (o repoda eşik üstü chunk yok) leksikal fallback yapma.
        if source_filter:
            return "", ""
        return _leksikal_fallback(soru, collection)

    # Kod retrieval için: tek dosyaya çoğunluk oyu uygulama; tüm alakalı chunk'ları
    # birleştir (soru birden çok dosyadaki ilgili kodu gerektirebilir).
    if not majority_vote:
        kaynaklar = sorted({s for _, s in secilenler if s})
        return "\n\n".join(d for d, _ in secilenler), ", ".join(kaynaklar)

    kaynak_sayaci = Counter(source for _, source in secilenler)
    max_sayi = max(kaynak_sayaci.values())
    adaylar = [s for s, n in kaynak_sayaci.items() if n == max_sayi]

    if len(adaylar) == 1:
        cogunluk_source = adaylar[0]
    else:
        cogunluk_source = _lexikal_tie_break(adaylar, secilenler, soru)

    filtrelenmis = [doc for doc, s in secilenler if s == cogunluk_source]
    return "\n\n".join(filtrelenmis), cogunluk_source
