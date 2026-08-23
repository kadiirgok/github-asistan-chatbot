# -*- coding: utf-8 -*-
"""RAG orkestrasyonu: tek koleksiyonda cevap + web fallback.

İki katmanlı akış (README -> kod -> web) GithubRag.ask() içinde kurulur; burada
yalnızca tek koleksiyonda cevap üretme (answer_from_collection) ve web fallback
(answer_from_web) yardımcıları bulunur.
"""

from .prompts import PROMPT_TEMPLATE, SYSTEM_PROMPT, WEB_PROMPT_TEMPLATE
from .retrieval import retrieve
from .validation import (
    dogrula_eksik_deger,
    dogrula_konu_uyumu,
    dogrula_sayisal_tutarlilik,
)
from .web_search import web_search_araci


def _llm_cevap(llm, context: str, soru: str, max_tokens: int,
               prompt_template: str = PROMPT_TEMPLATE, temperature: float = 0.3,
               repeat_penalty: float = 1.1, top_p: float = 0.9) -> str:
    """Bağlam + soruyu şablona koyup modelden cevap üretir.

    Sistem mesajı modeli tek davranışa sabitler (yalnızca bağlam, uydurma yok);
    küçük modellerdeki "bilmiyorum ama cevaplıyorum" tarzı çelişkili girişleri azaltır.
    `repeat_penalty` Qwen ailesi için ~1.1 daha doğaldır (1.3 kelime bozulmasına yol açar).
    """
    prompt = prompt_template.format(context=context, soru=soru)
    try:
        cevap = llm.complete(
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            repeat_penalty=repeat_penalty,
            top_p=top_p,
        )
    except Exception as exc:  # noqa: BLE001 — model çağrısı hatasını üst katmana bildir
        raise RuntimeError(f"Model cevap üretirken hata oluştu: {exc}") from exc
    cevap = (cevap or "").strip()
    if not cevap:
        # Arka uç boş dönebilirse bile arayüze boş cevap gitmesin.
        return "Bu konuda yeterli bir yanıt üretemedim. Lütfen soruyu farklı biçimde tekrar sorun."
    return cevap


def answer_from_collection(llm, soru: str, collection, bilinen_anahtarlar: list[str],
                           embedding_model: str, top_k: int = 4, max_tokens: int = 220,
                           esik: float = 0.4, majority_vote: bool = True,
                           source_filter: str | None = None,
                           dogrula_sayisal: bool = True,
                           prompt_template: str = PROMPT_TEMPLATE) -> tuple[str, str, bool] | None:
    """Tek koleksiyonda RAG dener.

    Bağlam bulunamazsa veya konu uymazsa None döner (çağıran koda/web'e geçebilir).
    Aksi halde (cevap, "local", dogrulandi) döner. Kod katmanında sayısal denetim
    anlamsızdır (port/IP/sürüm gibi meşru sayılar içerir); bu yüzden dogrula_sayisal
    ile kapatılabilir ve farklı bir prompt (sentez) geçirilebilir.
    """
    context, source = retrieve(soru, collection, embedding_model, top_k=top_k, esik=esik,
                               majority_vote=majority_vote, source_filter=source_filter)
    if not context.strip():
        return None
    if not dogrula_konu_uyumu(soru, source, bilinen_anahtarlar):
        return None

    prompt_context = f"Kaynak: {source}\n\n{context}" if source else context
    try:
        cevap = _llm_cevap(llm, prompt_context, soru, max_tokens,
                           prompt_template=prompt_template, temperature=0.2)
    except Exception:
        return None

    if dogrula_sayisal:
        dogrulandi = (dogrula_sayisal_tutarlilik(cevap, context, soru)
                      and dogrula_eksik_deger(cevap, context))
    else:
        dogrulandi = True
    return cevap, "local", dogrulandi


def answer_from_web(llm, soru: str, bilinen_anahtarlar: list[str],
                    max_tokens: int = 220) -> tuple[str, str, bool]:
    """Web (DuckDuckGo) fallback: arama yapıp cevap üretir."""
    web_context = web_search_araci(soru)
    if not web_context.strip():
        return "Bu konuda elimde bilgi yok.", "none", True

    if not dogrula_konu_uyumu(soru, "web", bilinen_anahtarlar):
        return "Bu konuda elimde güvenilir bilgi yok.", "none", False

    try:
        cevap = _llm_cevap(llm, web_context, soru, max_tokens,
                           prompt_template=WEB_PROMPT_TEMPLATE, temperature=0.0)
    except Exception:
        return "Model şu anda yanıt üretemiyor (teknik bir sorun oluştu).", "web", False

    dogrulandi = (dogrula_sayisal_tutarlilik(cevap, web_context, soru)
                  and dogrula_eksik_deger(cevap, web_context))
    return cevap, "web", dogrulandi


def generate_answer(llm, soru: str, collection, bilinen_anahtarlar: list[str],
                    embedding_model: str, top_k: int = 4, max_tokens: int = 220,
                    esik: float = 0.4) -> tuple[str, str, bool]:
    """Tek koleksiyon (README) + web fallback. (basit tek-katman akışı)"""
    res = answer_from_collection(llm, soru, collection, bilinen_anahtarlar,
                                 embedding_model, top_k, max_tokens, esik)
    if res is not None:
        return res
    return answer_from_web(llm, soru, bilinen_anahtarlar, max_tokens)
