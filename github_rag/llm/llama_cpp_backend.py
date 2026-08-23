# -*- coding: utf-8 -*-
"""Yerel llama.cpp arka ucu (API anahtarı gerektirmez).

Model, makinedeki GGUF dosyasından llama-cpp-python ile yerelde çalıştırılır;
dışarıya istek atılmaz, kota/limit/anahtar yoktur. Llama nesnesi pahalı olduğu
için ilk çağrıda yüklenir ve süreç boyunca önbellekte tutulur. Üretim iş parçacığı
güvenli değildir, bu yüzden tek seferde tek üretim yapılır (kilit).
"""

import os
import threading

from .base import LLMBackend
from .errors import LLMRetryableError


class LlamaCppBackend(LLMBackend):
    """Tek bir yerel GGUF modelini llama-cpp-python ile çalıştıran arka uç."""

    def __init__(self, model_path: str, n_ctx: int = 4096, n_threads: int = 0,
                 n_gpu_layers: int = 0, verbose: bool = False):
        self._model_path = model_path
        self._n_ctx = n_ctx
        self._n_threads = n_threads or (os.cpu_count() or 4)
        self._n_gpu_layers = n_gpu_layers
        self._verbose = verbose
        self._llm = None
        self._lock = threading.Lock()

    def _ensure_loaded(self):
        if self._llm is not None:
            return
        if not os.path.isfile(self._model_path):
            raise RuntimeError(
                f"Model dosyası bulunamadı: {self._model_path}\n"
                "LLAMA_MODEL_PATH ile mevcut bir GGUF dosyasını gösterin."
            )
        from llama_cpp import Llama  # geç yüklenir (import ağırdır)

        self._llm = Llama(
            model_path=self._model_path,
            n_ctx=self._n_ctx,
            n_threads=self._n_threads,
            n_gpu_layers=self._n_gpu_layers,
            verbose=self._verbose,
        )

    def complete(self, messages, max_tokens, temperature, repeat_penalty=1.1, top_p=0.9):
        with self._lock:
            try:
                self._ensure_loaded()
                sonuc = self._llm.create_chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    repeat_penalty=repeat_penalty,
                    top_p=top_p,
                )
            except Exception as exc:  # noqa: BLE001 — yükleme/üretim hatasını üst katmana bildir
                raise LLMRetryableError(f"llama.cpp üretim hatası: {exc}") from exc

        try:
            content = sonuc["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMRetryableError("llama.cpp bozuk yanıt gövdesi") from exc

        content = (content or "").strip()
        if not content:
            raise LLMRetryableError("llama.cpp boş yanıt gövdesi")
        return content
