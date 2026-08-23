# -*- coding: utf-8 -*-
"""LLM çağrıları için hata sınıfları.

Yedek zincir (FallbackBackend) bu hatalara bakarak karar verir:
- Retryable: aynı sağlayıcıda birkaç kez tekrar dene (429 / 5xx / timeout / bağlantı).
- Fatal: deterministik hata (kötü anahtar/model/rota) — anında bir sonraki sağlayıcıya geç.
"""


class LLMError(Exception):
    """Tüm LLM arka ucu hatalarının tabanı."""


class LLMRetryableError(LLMError):
    """Geçici hata: 429, 5xx, timeout, bağlantı kopması veya bozuk yanıt gövdesi."""


class LLMFatalError(LLMError):
    """Kalıcı hata: 400, 401, 403, 404. Tekrar denemek anlamsızdır."""
