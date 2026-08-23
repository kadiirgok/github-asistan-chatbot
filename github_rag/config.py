# -*- coding: utf-8 -*-
"""Çalışma zamanı ayarları.

Tüm yapılandırma tek yerde toplanır: LLM sağlayıcıları (DeepSeek/Groq), embedding modeli,
ChromaDB klasörü, GitHub token'ı ve eşikler. Değer önceliği: açık parametre >
ortam değişkeni > .env > varsayılan.
"""

import os
from dataclasses import dataclass
from pathlib import Path

# Proje kökü: github_rag/ klasörünün bir üstü
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHROMA_DIR = PROJECT_ROOT / "chroma_db"

# Çok dilli embedding: Türkçe soru -> İngilizce README eşleşmesini de destekler
DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Cosine mesafe eşiği (1 - kosinüs benzerliği). Küçük = daha alakalı.
DEFAULT_DISTANCE_THRESHOLD = 0.4


def _load_dotenv(path: Path | None = None) -> dict[str, str]:
    """Proje kökündeki .env dosyasını (varsa) KEY=VALUE biçiminde okur."""
    p = path or (PROJECT_ROOT / ".env")
    out: dict[str, str] = {}
    if not p.is_file():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _ensure_env_file() -> None:
    """.env yoksa .env.example'dan kopyalar (ilk çalıştırma deneyimini kolaylaştırır)."""
    env_path = PROJECT_ROOT / ".env"
    example_path = PROJECT_ROOT / ".env.example"
    if not env_path.is_file() and example_path.is_file():
        try:
            env_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            pass


@dataclass
class Config:
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    chroma_dir: str = str(DEFAULT_CHROMA_DIR)
    github_token: str = ""
    # LLM sağlayıcıları (OpenAI-uyumlu): DeepSeek (birincil) -> Groq (yedek).
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    llm_timeout: int = 120
    llm_retries: int = 1
    distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD
    top_k: int = 4
    max_tokens: int = 512
    code_max_files: int = 200        # kod okumada en fazla dosya sayısı
    code_max_size: int = 1_500_000   # kod okumada toplam byte sınırı (~1.5 MB)
    code_distance_threshold: float = 0.7   # kod retrieval eşiği (kod mesafeleri daha yüksek çıkar)
    code_top_k: int = 12             # kod retrieval'da dönen chunk sayısı (betimleme için daha geniş)


def _int_env(env: dict, key: str) -> int | None:
    try:
        return int(env[key])
    except (KeyError, ValueError):
        return None


def load_config() -> Config:
    """Ortam değişkenlerinden ve .env dosyasından Config üretir.

    Öncelik: gerçek ortam değişkenleri (örn. HF Spaces Secrets) > .env > varsayılan.
    .env yalnızca yerel geliştirme kolaylığıdır; ortamda ayarlı bir değer varsa o kazanır.
    """
    _ensure_env_file()
    env = _load_dotenv()
    env.update(os.environ)

    cfg = Config()
    if env.get("GITHUB_RAG_EMBEDDING_MODEL"):
        cfg.embedding_model = env["GITHUB_RAG_EMBEDDING_MODEL"]
    if env.get("GITHUB_RAG_CHROMA_DIR"):
        cfg.chroma_dir = env["GITHUB_RAG_CHROMA_DIR"]
    if env.get("GITHUB_TOKEN"):
        cfg.github_token = env["GITHUB_TOKEN"]

    if env.get("DEEPSEEK_API_KEY"):
        cfg.deepseek_api_key = env["DEEPSEEK_API_KEY"]
    if env.get("DEEPSEEK_MODEL"):
        cfg.deepseek_model = env["DEEPSEEK_MODEL"]
    if env.get("GROQ_API_KEY"):
        cfg.groq_api_key = env["GROQ_API_KEY"]
    if env.get("GROQ_MODEL"):
        cfg.groq_model = env["GROQ_MODEL"]
    if (t := _int_env(env, "GITHUB_RAG_LLM_TIMEOUT")) is not None:
        cfg.llm_timeout = t
    if (r := _int_env(env, "GITHUB_RAG_LLM_RETRIES")) is not None:
        cfg.llm_retries = r

    try:
        if env.get("GITHUB_RAG_MAX_TOKENS"):
            cfg.max_tokens = int(env["GITHUB_RAG_MAX_TOKENS"])
    except ValueError:
        pass
    try:
        if env.get("GITHUB_RAG_THRESHOLD"):
            cfg.distance_threshold = float(env["GITHUB_RAG_THRESHOLD"])
    except ValueError:
        pass
    return cfg
