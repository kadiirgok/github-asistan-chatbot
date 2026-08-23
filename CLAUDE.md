# CLAUDE.md

GitHub tabanlı RAG chatbot: bir GitHub kullanıcısının repolarını + README'lerini indeksleyip projeleri hakkında soru-cevap yapar. LLM: **DeepSeek (birincil) → Groq (yedek)** API zinciri.

## Mimari

- `github_rag/` — import edilebilir kütüphane (çekirdek mantık)
  - `__init__.py` — `GithubRag` sınıfı; iki katmanlı akış: README → (yetmezse) kod → (yoksa) web
  - `config.py` — tüm ayarlar; `load_config()` önceliği: **ortam değişkeni > `.env` > varsayılan**
  - `llm/` — arka uç: `base.py` (arayüz), `fallback.py` (yedek zincir), `openai_compat.py`, `errors.py`
  - `github.py` (repo/README/kod çekme), `indexing.py` (chunk+embedding+ChromaDB), `retrieval.py`, `answer.py`, `validation.py`, `prompts.py`, `web_search.py` (DuckDuckGo)
- `app/api.py` — FastAPI servisi (port 7860); statik UI `static/index.html`
- `Dockerfile` — HF Spaces deploy; `pyproject.toml` — kütüphane kurulumu

## Çalıştırma

- Yerel: `uvicorn app.api:app --reload` → http://127.0.0.1:8000
- Kurulum: `pip install -r requirements.txt` (opsiyonel: `pip install -e .`)

## Güvenlik (önemli)

- Repo **PUBLIC**. GitHub **push protection** aktif — secret içeren push otomatik reddedilir.
- `.env` (gerçek anahtarlar) gitignore'da, **asla commit edilmez**; repoda boş `.env.example` şablonu var.
- Anahtarlar: yerelde `.env`, deploy'da **HF Spaces → Settings → Variables and secrets** (ortam değişkeni olarak enjekte edilir, config.py otomatik okur).
- Yerel GGUF/llama.cpp arka ucu kaldırıldı — uygulama yalnızca API kullanır.

## İgnore edilenler

`models/` (12GB indirilmiş model), `venv/`, `chroma_db/`, `__pycache__/`, `.env`, `*.log`, `mobile/build/`.
