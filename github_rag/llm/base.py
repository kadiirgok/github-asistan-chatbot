# -*- coding: utf-8 -*-
"""LLM arka ucu arayüzü.

generate_answer yalnızca bu arayüzü bilir; böylece farklı arka uçlar
(llama.cpp, DeepSeek vb.) birbirinin yerine takılabilir olur.
"""

from abc import ABC, abstractmethod


class LLMBackend(ABC):
    """Mesaj listesinden metin cevabı üreten herhangi bir model arka ucu."""

    @abstractmethod
    def complete(self, messages: list[dict], max_tokens: int,
                 temperature: float, repeat_penalty: float = 1.1,
                 top_p: float = 0.9) -> str:
        """messages: [{"role": "system"/"user", "content": ...}] -> cevap metni."""
        raise NotImplementedError
