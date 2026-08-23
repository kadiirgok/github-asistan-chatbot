# -*- coding: utf-8 -*-
"""Sistem sağlama kontrolü.

LLM sağlayıcılarını (DeepSeek/Groq), GitHub API'sini ve yapılandırmayı hızlıca
test eder; neyin bozuk olduğunu ve nasıl düzeltileceğini net biçimde raporlar.

Kullanım:
    python scripts/check.py
"""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from github_rag.config import load_config

GITHUB_API = "https://api.github.com"


def _llm_test(name: str, url: str, key: str, model: str) -> tuple[str, str]:
    """Tek bir LLM sağlayıcısını 1 token'lık istekle test eder; (durum, açıklama) döner."""
    if not key:
        return "SKIP", "anahtar tanımlı değil (.env'e eklenebilir)"
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model,
                  "messages": [{"role": "user", "content": "ping"}],
                  "max_tokens": 5},
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001 — ağ hatasını net mesaja çevir
        return "FAIL", f"bağlantı hatası: {type(exc).__name__} {str(exc)[:80]}"

    if r.status_code == 200:
        return "OK", f"model {model!r} yanıt veriyor"
    if r.status_code in (401, 403):
        return "FAIL", f"anahtar geçersiz (HTTP {r.status_code}) — yeni anahtar al"
    if r.status_code == 404:
        return "FAIL", (f"model bulunamadı (HTTP 404) — {model!r} artık yok; "
                        f"console.groq.com'dan güncel bir model seç")
    return "FAIL", f"HTTP {r.status_code}: {r.text[:120]}"


def main() -> int:
    cfg = load_config()
    print("=" * 62)
    print("SİSTEM SAĞLAMA KONTROLÜ")
    print("=" * 62)

    ok_sayisi = 0
    saglayicilar = [
        ("DeepSeek", "https://api.deepseek.com/chat/completions",
         cfg.deepseek_api_key, cfg.deepseek_model),
        ("Groq", "https://api.groq.com/openai/v1/chat/completions",
         cfg.groq_api_key, cfg.groq_model),
    ]
    for name, url, key, model in saglayicilar:
        durum, aciklama = _llm_test(name, url, key, model)
        if durum == "OK":
            ok_sayisi += 1
        print(f"\n[{name}] model={model}")
        print(f"  -> {durum}: {aciklama}")

    print("\n[GitHub API]")
    try:
        g = requests.get(f"{GITHUB_API}/rate_limit", timeout=20)
        if g.status_code == 200:
            remaining = g.json().get("resources", {}).get("core", {}).get("remaining", "?")
            print(f"  -> OK: erişim var (kalan istek: {remaining})")
        else:
            print(f"  -> FAIL: HTTP {g.status_code}")
    except Exception as exc:  # noqa: BLE001
        print(f"  -> FAIL: bağlantı hatası {type(exc).__name__}")

    print("\n" + "=" * 62)
    if ok_sayisi >= 1:
        print(f"SONUÇ: TAMAM — {ok_sayisi} LLM sağlayıcısı çalışıyor. Sistem hazır.")
        return 0
    print("SONUÇ: HATA — çalışan LLM sağlayıcısı yok.")
    print("  Çözüm: .env dosyasına geçerli bir DEEPSEEK_API_KEY veya GROQ_API_KEY ekle.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
