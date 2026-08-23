# -*- coding: utf-8 -*-
"""OpenAI-uyumlu tek sağlayıcı arka ucu (DeepSeek vb.).

DeepSeek, OpenAI Chat Completions biçimini konuşur; yalnızca taban URL, anahtar ve
model değişir. `repeat_penalty` arayüzde tutulur ama gönderilmez: OpenAI-uyumlu uçlar
bilinmeyen alanları reddeder.
"""

import re

import requests

from .base import LLMBackend
from .errors import LLMFatalError, LLMRetryableError


def _strip_think(content: str) -> str:
    """Akıl yürütme modellerinin (Qwen3 vb.) <think>...</think> bloğunu ayıklar.

    Bu modeller cevabın başına düşünme sürecini <think> etiketleri içinde yazar;
    kullanıcıya yalnızca asıl cevap gösterilmelidir.
    """
    content = re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL)
    # Kapanış etiketi olmadan kesilen düşünme bloğunu da temizle.
    content = re.sub(r"<think>.*$", "", content or "", flags=re.DOTALL)
    return content.strip()


class OpenAICompatBackend(LLMBackend):
    """Tek bir OpenAI-uyumlu chat-completions sağlayıcısı."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 60):
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def complete(self, messages, max_tokens, temperature, repeat_penalty=1.1, top_p=0.9):
        try:
            resp = requests.post(
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                },
                timeout=self._timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise LLMRetryableError(f"Zaman aşımı: {self._url}") from exc
        except requests.exceptions.ConnectionError as exc:
            raise LLMRetryableError(f"Bağlantı hatası: {self._url}") from exc
        except requests.exceptions.RequestException as exc:
            raise LLMRetryableError(f"İstek hatası: {self._url}: {exc}") from exc

        if resp.status_code == 429 or resp.status_code >= 500:
            raise LLMRetryableError(f"HTTP {resp.status_code} ({self._model})")
        if resp.status_code in (400, 401, 403, 404):
            raise LLMFatalError(f"HTTP {resp.status_code} ({self._model})")
        if resp.status_code != 200:
            raise LLMRetryableError(f"Beklenmeyen HTTP {resp.status_code} ({self._model})")

        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMRetryableError("Bozuk yanıt gövdesi") from exc
        content = _strip_think(content)
        if not content or not content.strip():
            # Reasoning modelleri bazen yalnızca "düşünüp" boş content dönebilir;
            # bunu retryable say ki yedek zincir yeniden denesin.
            raise LLMRetryableError("Boş yanıt gövdesi")
        return content
