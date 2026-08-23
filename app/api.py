# -*- coding: utf-8 -*-
"""FastAPI katmanı: /health, /ingest, /chat + statik arayüz.

İş mantığı github_rag paketindedir; bu dosya yalnızca HTTP tarafını içerir.
"""

import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# `uvicorn app.api:app` ile çalıştırılırken github_rag paketinin bulunabilmesi için
# proje kökünü sys.path'in başına ekle.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from github_rag import GithubRag  # noqa: E402
from github_rag.config import load_config  # noqa: E402

STATIC_DIR = PROJECT_ROOT / "static"

config = load_config()
active_rag: GithubRag | None = None


def _last_target_path() -> Path:
    return Path(config.chroma_dir) / "last_target.txt"


def _save_last_target(hedef: str) -> None:
    try:
        _last_target_path().write_text(hedef.strip(), encoding="utf-8")
    except Exception:  # noqa: BLE001 — işaret dosyası yazılamasa da ingest başarılı sayılır
        pass


def _load_last_target() -> str | None:
    p = _last_target_path()
    if p.is_file():
        t = p.read_text(encoding="utf-8").strip()
        return t or None
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Son yüklenen hedefi ChromaDB'den (cache) geri kur — GitHub çağrısı yapmaz.
    global active_rag
    hedef = _load_last_target()
    if hedef:
        try:
            rag = GithubRag(config=config)
            rag.index(hedef)  # koleksiyon dolu -> cache dalı
            active_rag = rag
            print(f"Son hedef yeniden yüklendi: {hedef}")
        except Exception as exc:  # noqa: BLE001 — bozuk işaret dosyası startup'ı çökertmesin
            print(f"Son hedef yüklenemedi ({hedef}): {exc}")
    yield


app = FastAPI(title="GitHub RAG API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestRequest(BaseModel):
    hedef: str
    force: bool = False


class RefreshRequest(BaseModel):
    hedef: str = ""


class SoruRequest(BaseModel):
    soru: str


class CevapResponse(BaseModel):
    cevap: str
    kaynak: str
    sure_saniye: float
    dogrulandi: bool


@app.get("/health")
def health():
    return {"durum": "hazir"}


@app.post("/ingest")
def ingest(req: IngestRequest):
    """GitHub kullanıcı adı / linki alır, repo+README'leri indeksler ve aktif yapar."""
    global active_rag
    t0 = time.time()
    try:
        rag = GithubRag(config=config)
        repo_sayisi = rag.index(req.hedef, force=req.force)
        active_rag = rag
        _save_last_target(req.hedef)
    except Exception as exc:  # noqa: BLE001 — kullanıcıya anlaşılır hata döndür
        return JSONResponse(status_code=400, content={"durum": "hata", "mesaj": str(exc)})
    return {"durum": "tamam", "hedef": req.hedef, "repo_sayisi": repo_sayisi,
            "repolar": sorted(active_rag.repo_names),
            "sure_saniye": round(time.time() - t0, 2)}


@app.post("/chat", response_model=CevapResponse)
def chat(req: SoruRequest):
    """Aktif indeks üzerinden soruyu RAG ile yanıtlar."""
    global active_rag
    if active_rag is None:
        return CevapResponse(cevap="Önce bir GitHub kullanıcı adı veya linki yükleyin.",
                             kaynak="none", sure_saniye=0.0, dogrulandi=False)
    res = active_rag.ask(req.soru)
    return CevapResponse(**res)


@app.get("/repos")
def repos():
    """Aktif hedefin repo listesini metadata (dil/açıklama/yıldız) ile döndürür."""
    global active_rag
    if active_rag is None:
        return JSONResponse(status_code=400, content={"durum": "hata",
                                                       "mesaj": "Önce bir GitHub hedefi yükleyin."})
    return {"durum": "tamam", "hedef": active_rag.target,
            "repolar": sorted(active_rag.repo_metadata, key=lambda m: -(m.get("stars", 0) or 0))}


@app.get("/profile")
def profile():
    """Aktif hedefin toplu özetini döndürür: dil dağılımı, yıldız, repo listesi."""
    global active_rag
    if active_rag is None:
        return JSONResponse(status_code=400, content={"durum": "hata",
                                                       "mesaj": "Önce bir GitHub hedefi yükleyin."})
    return {"durum": "tamam", "hedef": active_rag.target, **active_rag.profile()}


@app.get("/check-updates")
def check_updates(hedef: str = ""):
    """Cache'li hedef ile GitHub'daki güncel durum arasındaki farkı döndürür (kuru koşu)."""
    global active_rag
    if active_rag is None:
        return JSONResponse(status_code=400, content={"durum": "hata",
                                                       "mesaj": "Önce bir GitHub hedefi yükleyin."})
    return {"durum": "tamam", **active_rag.detect_changes(hedef or None)}


@app.post("/refresh")
def refresh(req: RefreshRequest):
    """Değişiklik varsa hedefi temiz şekilde yeniden indeksler; yoksa 'guncel' döner."""
    global active_rag
    if active_rag is None:
        return JSONResponse(status_code=400, content={"durum": "hata",
                                                       "mesaj": "Önce bir GitHub hedefi yükleyin."})
    hedef = req.hedef or active_rag.target
    diff = active_rag.detect_changes(hedef)
    if not diff["guncel"]:
        active_rag.index(hedef, force=True)
    return {"durum": "tamam", **diff, "repo_sayisi": active_rag.repo_sayisi}


@app.exception_handler(Exception)
async def genel_hata_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "cevap": "Sunucu beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.",
            "kaynak": "none",
            "sure_saniye": 0.0,
            "dogrulandi": False,
        },
    )


# Statik arayüz en sona mount edilir ki API rotaları önce eşleşsin.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
