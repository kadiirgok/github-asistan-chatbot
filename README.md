# GitHub Asistanı (github-rag)

Bir GitHub kullanıcı adı veya linki ver; sistem o kişinin **repolarını ve README'lerini** otomatik çeker, indeksler ve projeleri hakkında soru sorabilmeni sağlar. README yetmezse **kaynak koda** geçer. DeepSeek + Groq API ile çalışır; `pip install` ile **kütüphane** gibi de import edilebilir.

## 🔗 Canlı demo

👉 **https://akadirgok-github-asistani.hf.space**

Yukarıdaki bağlantıya tıklayıp doğrudan deneyebilirsin; kurulum gerekmez. Yerel olarak çalıştırmak için aşağıdaki **Kurulum** bölümüne bak.

## Özellikler

- 🔗 **Dinamik GitHub** — kullanıcı adı / repo linki → repo + README'ler otomatik çekilir (GitHub API).
- 🧠 **İki katmanlı RAG** — `README → (yetmezse) Kod → (hiç yoksa) Web`.
- 💬 **Takip soruları** — "hizmet gelsin ne işe yarıyor?" → "özellikleri neler?" gibi repo adı olmayan devam soruları önceki repoya bağlanır.
- 🔢 **Meta sorular** — "kaç repo var?", "hangi projeler var?" doğrudan indeksten cevaplanır.
- ✅ **3 katmanlı doğrulama** — sayı tutarlılığı, eksik değer, konu uyumu; asla sessizce yanlış bilgi vermez.
- 🔌 **DeepSeek + Groq** — OpenAI-uyumlu API; DeepSeek birincil, Groq yedek; geçici hatalarda otomatik yeniden dener.

## Nasıl çalışır

```
GitHub kullanıcı adı / link
        │
        ▼
   GitHub API: repo listesi + README'ler            (github_rag/github.py)
        │
        ▼
   README'ler chunk'lanır, çok dilli embedding ile vektöre çevrilir,
   kullanıcı başına ayrı koleksiyonda ChromaDB'ye yazılır  (github_rag/indexing.py)
        │
        ▼
   Soru → en alakalı chunk'lar (cosine + repo çoğunluk oyu)   (github_rag/retrieval.py)
        │
        ├─ README'de doğrulanmış cevap var → cevabı döndür
        │
        ├─ Yetmediyse ve soru bir repoyu adlandırıyorsa →
        │      o reponun KAYNAK KODU çekilir + indekslenir → koddan cevap
        │
        └─ Hiç yoksa → DuckDuckGo (web) fallback
        │
        ▼
   DeepSeek/Groq LLM bağlama dayanarak cevap üretir   (github_rag/answer.py)
        │
        ▼
   3 katmanlı doğrulama (sayı / eksik değer / konu uyumu)
        │
        ▼
   Cevap + şeffaf rozet: kaynak (local/web/none), doğrulandı, süre
```

Doğrulanamayan cevap da gösterilir ama "Doğrulanamadı" rozetiyle işaretlenir (sayı tutarlılığı / konu uyumu denetimi).

## Kurulum

```bash
# 1) Ortam oluştur (varsa atla)
python -m venv venv
venv\Scripts\activate            # Windows

# 2) Bağımlılıkları kur
pip install -r requirements.txt

# 3) (İsteğe bağlı) paketi kütüphane olarak kur
pip install -e .
```

`.env` ilk çalıştırmada `.env.example`'dan otomatik oluşturulur. İçine kendi `DEEPSEEK_API_KEY`
değerini yapıştır; anahtarsız da uygulama açılır ve repo listesi/dil dağılımı soruları çalışır
(yalnızca LLM cevabı anahtar ister).

## Kütüphane olarak kullanım

```python
from github_rag import GithubRag

# Bir kullanıcıyı veya tek repo linkini indeksle
rag = GithubRag.from_github("kadiirgok")        # veya "https://github.com/kadiirgok/bilgi-tr"

# Soru sor
res = rag.ask("hangi dillerde yazılmış?")
print(res["cevap"])            # akıcı cevap
print(res["kaynak"])           # "local" | "web" | "none"
print(res["dogrulandi"])       # doğrulama sonucu
```

Yerel `.txt` klasörünü (örnek veri / test) indekslemek için: `GithubRag.from_local_folder("data")`.

## Web arayüzü

```bash
uvicorn app.api:app --reload
```

Tarayıcıda `http://127.0.0.1:8000` aç → GitHub kullanıcı adı/linki yaz → **Yükle** → soru sor.

### API uç noktaları

| Metod | Yol | Gövde | Yanıt |
|---|---|---|---|
| GET | `/health` | — | `{"durum": "hazir"}` |
| POST | `/ingest` | `{"hedef": "kadiirgok", "force": false}` | `{"durum","hedef","repo_sayisi","repolar","sure_saniye"}` |
| POST | `/chat` | `{"soru": "..."}` | `{"cevap","kaynak","sure_saniye","dogrulandi"}` |
| GET | `/repos` | — | `{"durum","hedef","repolar"}` |
| GET | `/profile` | — | `{"durum","repo_sayisi","diller","toplam_yildiz","repolar"}` |
| GET | `/check-updates` | — | `{"durum","eklenen","kaldirilan","degisen","guncel"}` |
| POST | `/refresh` | `{"hedef": ""}` | `{"durum","eklenen","kaldirilan","degisen","guncel","repo_sayisi"}` |

## Yapılandırma (`.env`)

> ⚠️ **Güvenlik:** `.env` (gerçek anahtarlar) asla Git'e commit edilmez. `.gitignore` ve
> `.dockerignore` onu hariç tutar; repoda yalnızca boş değerli `.env.example` şablonu bulunur.
> Bir anahtar bir kez bile repoya girerse onu sıfırla (rotate) ve yenisini üret.

`.env.example` dosyasını `.env` olarak kopyala; tüm değerler isteğe bağlıdır:

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `DEEPSEEK_API_KEY` | (yok) | DeepSeek API anahtarı (birincil) |
| `DEEPSEEK_MODEL` | `deepseek-chat` | DeepSeek modeli |
| `GROQ_API_KEY` | (yok) | Groq API anahtarı (yedek, boş bırakılabilir) |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Groq modeli |
| `GITHUB_TOKEN` | (yok) | GitHub API limitini 60/saat → 5000/saat yapar |
| `GITHUB_RAG_EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Çok dilli embedding |
| `GITHUB_RAG_MAX_TOKENS` | `512` | LLM cevap uzunluğu |

Öncelik sırası **gerçek ortam değişkeni > `.env` > varsayılan** şeklindedir. Deploy'da
HF Spaces **Secrets** ile tanımladığın değişkenler, `.env`'de ne yazarsa yazsın önce gelir —
`.env` yalnızca yerel geliştirme içindir.

## LLM arka ucu (DeepSeek + Groq)

Uygulama OpenAI-uyumlu API'leri kullanır: **DeepSeek birincil, Groq yedek**. Anahtarı
ayarlı olmayan sağlayıcı atlanır. Geçici hatalarda (HTTP 429/5xx, zaman aşımı, boş yanıt)
arka uç otomatik yeniden dener; kalıcı hatalarda (401/403) sıradaki sağlayıcıya geçer.
Yedek zincir altyapısı `llm/fallback.py` ve `llm/openai_compat.py` üzerinde kuruludur.

## Proje yapısı

```
github_rag/            # kütüphane (import edilebilir)
├── __init__.py        #   GithubRag (iki katmanlı akış + takip bağlamı)
├── config.py          #   ayarlar + .env
├── github.py          #   GitHub API: repo/README + kaynak kod çekme
├── indexing.py        #   chunk + embedding + ChromaDB
├── retrieval.py       #   vektör arama + eşik + repo çoğunluk oyu
├── validation.py      #   3 katmanlı doğrulama
├── answer.py          #   RAG orkestrasyonu + web fallback
├── prompts.py         #   prompt şablonları
├── web_search.py      #   DuckDuckGo fallback
└── llm/               #   LLM arka ucu (DeepSeek + Groq)
app/                   # FastAPI + statik arayüz
static/                # tek dosyalık web UI
```

## Deploy (Hugging Face Spaces)

Anahtar GitHub'a **girmez**; uygulama HF Spaces'ta çalışır, kullanıcılar sadece linke tıklar.

1. Hugging Face'te hesap aç → **New Space** (SDK: **Docker**, Visibility: **Public**).
2. Space **Settings → Variables and secrets** → `DEEPSEEK_API_KEY` (ve istersen `GROQ_API_KEY`, `GITHUB_TOKEN`) ekle.
3. Space'i bu GitHub repo'suna bağla (veya Space'in kendi git'ine push et). `Dockerfile` otomatik build eder (FastAPI + `static/index.html`).
4. Deploy bitince linkini README'nin üstündeki **Canlı demo** bölümüne yaz.

## Notlar / bilinen sınırlar

- Önceki sürümdeki yerel GGUF model arka ucu (llama.cpp) kaldırıldı; uygulama artık yalnızca API (DeepSeek + Groq) kullanır.
- Çapraz repo karşılaştırma soruları ("A ile B'yi karşılaştır") tek repoya iner.
- Kod okuma repo başına bir kez yapılır (önbellekli); büyük repolar için `config.py` içindeki `code_max_files` / `code_max_size` sınırları uygulanır.
- GitHub API token'sız 60 istek/saat ile sınırlıdır; büyük hesaplar için `GITHUB_TOKEN` önerilir.
- İlk kez okunan bir reponun kaynak kodu bir kez çekilip indekslenir (sonra önbellekten hızlı).
- Yüklenen hedef sunucu yeniden başlasa da ChromaDB'den geri yüklenir; `/refresh` ile GitHub'daki değişiklikler çekilir.
