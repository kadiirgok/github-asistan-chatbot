# -*- coding: utf-8 -*-
"""LLM arka ucu fabrikası: OpenAI-uyumlu API zinciri kurar (DeepSeek -> Groq)."""

from .base import LLMBackend
from .errors import LLMError, LLMFatalError, LLMRetryableError
from .fallback import FallbackBackend
from .openai_compat import OpenAICompatBackend

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def make_llm(config) -> LLMBackend:
    """API sağlayıcılarından yedek zinciri kurar: DeepSeek (birincil) -> Groq (yedek).

    Her ikisi de OpenAI-uyumlu chat-completions konuşur; yalnızca taban URL, anahtar
    ve model değişir. Anahtarı ayarlı olmayan sağlayıcı atlanır; hiçbiri yoksa net
    bir hata fırlatılır. FallbackBackend geçici hatalarda (429/5xx/timeout) yeniden
    dener, kalıcı hatalarda (401/403) sıradaki sağlayıcıya geçer.
    """
    backends: list[LLMBackend] = []
    if config.deepseek_api_key:
        backends.append(OpenAICompatBackend(
            DEEPSEEK_BASE_URL, config.deepseek_api_key, config.deepseek_model,
            timeout=config.llm_timeout))
    if config.groq_api_key:
        backends.append(OpenAICompatBackend(
            GROQ_BASE_URL, config.groq_api_key, config.groq_model,
            timeout=config.llm_timeout))
    if not backends:
        raise ValueError(
            "En az bir LLM API anahtarı gerekli: .env dosyasına DEEPSEEK_API_KEY "
            "ve/veya GROQ_API_KEY ekleyin."
        )
    return FallbackBackend(backends, retries=config.llm_retries)


__all__ = [
    "LLMBackend", "OpenAICompatBackend", "FallbackBackend",
    "LLMError", "LLMRetryableError", "LLMFatalError", "make_llm",
]
