# -*- coding: utf-8 -*-
"""Sağlayıcı yedek zinciri: biri kota/limit verince sıradakine geçer."""

import time

from .base import LLMBackend
from .errors import LLMFatalError, LLMRetryableError


class FallbackBackend(LLMBackend):
    """Birden çok LLM arka ucunu sırayla dener.

    Politika:
    - Retryable hata (429/5xx/timeout/bağlantı): aynı sağlayıcıda `retries` kadar
      lineer geri çekilme (backoff) ile tekrar dene; yine olmazsa sonrakine geç.
    - Fatal hata (401/403/404): anında sonraki sağlayıcıya geç.
    - Tümü başarısızsa tek ve net bir RuntimeError fırlat.
    """

    def __init__(self, backends: list, retries: int = 1, backoff: float = 0.5):
        if not backends:
            raise ValueError("FallbackBackend en az bir arka uç ister.")
        self._backends = backends
        self._retries = retries
        self._backoff = backoff

    def complete(self, messages, max_tokens, temperature, repeat_penalty=1.1, top_p=0.9):
        son_hata = None
        for backend in self._backends:
            for deneme in range(self._retries + 1):
                try:
                    return backend.complete(
                        messages, max_tokens, temperature, repeat_penalty, top_p)
                except LLMRetryableError as exc:
                    son_hata = exc
                    if deneme < self._retries:
                        time.sleep(self._backoff * (deneme + 1))
                        continue
                except LLMFatalError as exc:
                    son_hata = exc
                break  # bu sağlayıcı bitti -> sonrakine geç
        raise RuntimeError(f"Tüm LLM sağlayıcıları başarısız oldu: {son_hata}")
