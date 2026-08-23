# -*- coding: utf-8 -*-
"""HF Spaces için Gradio arayüzü (ÜCRETSİZ deploy).

HF Spaces'ta "Gradio" SDK ücretsizdir; "Docker" SDK ücretli. Bu dosya Gradio
SDK ile çalışır ve aynı `github_rag` kütüphanesini kullanır. API anahtarları
HF Spaces "Variables and secrets" üzerinden ortam değişkeni olarak verilir
(config.py bunları otomatik okur).
"""
import gradio as gr

from github_rag import GithubRag
from github_rag.config import load_config

_config = load_config()
_rag: GithubRag | None = None


def yukle(hedef: str) -> str:
    """GitHub hedefini çekip indeksler; kısa özet döndürür."""
    global _rag
    hedef = (hedef or "").strip()
    if not hedef:
        return "Lütfen bir GitHub kullanıcı adı veya repo linki girin."
    try:
        r = GithubRag(target=hedef, config=_config)
        n = r.index(hedef)
        _rag = r
        profil = r.profile()
        diller = ", ".join(f"{d} ({k})" for d, k in profil.get("diller", {}).items())
        return (f"✅ **{n} repo** yüklendi: `{hedef}`\n\n"
                f"- Toplam yıldız: {profil.get('toplam_yildiz', 0)}\n"
                f"- Diller: {diller or '—'}")
    except Exception as e:  # noqa: BLE001 — kullanıcıya net mesaj
        return f"❌ Yükleme hatası: {e}"


def cevapla(soru: str, history) -> str:
    """Yüklenen hedef üzerinde soruyu RAG ile yanıtlar."""
    if _rag is None:
        return "Önce bir GitHub kullanıcı adı yükleyin (yukarıya yazıp **Yükle**'ye basın)."
    try:
        res = _rag.ask(soru)
        cevap = res.get("cevap", "")
        kaynak = res.get("kaynak", "none")
        dogrulandi = res.get("dogrulandi", False)
        rozet = "✅ doğrulandı" if dogrulandi else "⚠️ doğrulanamadı"
        return f"{cevap}\n\n_{rozet} · kaynak: {kaynak}_"
    except Exception as e:  # noqa: BLE001
        return f"❌ Hata: {e}"


with gr.Blocks(title="GitHub Asistanı") as demo:
    gr.Markdown(
        "# 🤖 GitHub Asistanı\n"
        "Bir GitHub kullanıcı adı / repo linki yaz, o kişinin projelerini "
        "indeksleyip hakkında soru sor."
    )
    with gr.Row():
        hedef = gr.Textbox(
            label="GitHub kullanıcı adı veya repo linki",
            placeholder="örn. kadiirgok",
            scale=3,
        )
        yukle_btn = gr.Button("Yükle", scale=1)
    durum = gr.Markdown()
    yukle_btn.click(fn=yukle, inputs=hedef, outputs=durum)
    hedef.submit(fn=yukle, inputs=hedef, outputs=durum)

    gr.ChatInterface(
        fn=cevapla,
        title="Soru sor",
        examples=["hangi dillerde yazılmış?", "kaç repo var?"],
    )


if __name__ == "__main__":
    demo.launch()
