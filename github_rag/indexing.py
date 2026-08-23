# -*- coding: utf-8 -*-
"""Metin parçalama + embedding + ChromaDB indeksleme.

Koleksiyonlar kullanıcı/repo başına ayrılır (repos_<hedef>) ve cosine uzayında
açılır; embedding modeli çok dillidir (Türkçe soru -> İngilizce README eşleşir).
"""

import hashlib

import chromadb
from sentence_transformers import SentenceTransformer

_embedding_model = None
_embedding_model_name = None


def _get_embedding_model(name: str):
    """Embedding modelini ilk çağrıda yükler ve isim değişmediği sürece önbelleğe alır."""
    global _embedding_model, _embedding_model_name
    if _embedding_model is None or _embedding_model_name != name:
        print(f"Embedding modeli yükleniyor: {name} (ilk sefer sürebilir)...")
        _embedding_model = SentenceTransformer(name)
        _embedding_model_name = name
    return _embedding_model


def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    """Uzun metni kelime bazında, örtüşmeyle parçalara böler."""
    words = text.split()
    if not words:
        return []

    chunks = []
    step = max(1, chunk_size - overlap)
    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        if i + chunk_size >= len(words):
            break
    return chunks


def _chunk_id(source: str, text: str) -> str:
    """Chunk'a, kaynağıyla birlikte kararlı bir kimlik üretir.

    Aynı kaynaktaki aynı chunk tekrar indekslenince aynı id'yi alır (upsert ile
    güncellenir); farklı repolardaki özdeş metinler ise çakışmaz (source eklenir).
    """
    return hashlib.sha1(f"{source}\x00{text}".encode("utf-8")).hexdigest()


def get_collection(chroma_dir: str, collection_name: str):
    """Belirtilen koleksiyonu açar (yoksa cosine uzayında oluşturur)."""
    client = chromadb.PersistentClient(path=chroma_dir)
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def clear_collection(chroma_dir: str, collection_name: str) -> None:
    """Koleksiyondaki tüm dokümanları siler (force yeniden çekimden önce).

    `build_index` yalnızca upsert yapar; silinen repo / değişen README eski
    chunk'ları öksüz bırakır. Deterministik olması için id'ler alınıp tek tek
    silinir (`delete(where={})` davranışı ChromaDB sürümleri arasında değişebilir).
    """
    c = get_collection(chroma_dir, collection_name)
    ids = c.get(include=[])["ids"]
    if ids:
        c.delete(ids=ids)


def reset_collection(chroma_dir: str, collection_name: str):
    """Koleksiyonu silip yeniden oluşturur (bozuk HNSW indeksini onarmak için)."""
    client = chromadb.PersistentClient(path=chroma_dir)
    try:
        client.delete_collection(collection_name)
    except Exception:  # noqa: BLE001 — yoksa zaten sorun değil
        pass
    return get_collection(chroma_dir, collection_name)


def build_index(documents: list, chroma_dir: str, collection_name: str,
                embedding_model: str, chunk_size: int = 300, overlap: int = 50) -> int:
    """Dokümanları chunk'lar, embed eder ve koleksiyona yazar; chunk sayısını döndürür.

    `documents` öğeleri {"text", "source", "url"} sözlükleri olmalıdır.
    Kod için daha küçük chunk_size (ör. 150) kullanılır: kod token yoğun olduğu
    için aynı kelime sayısı çok daha fazla token üretir ve model bağlamını taşırır.
    """
    model = _get_embedding_model(embedding_model)
    collection = get_collection(chroma_dir, collection_name)

    ids, texts, metadatas = [], [], []
    for doc in documents:
        text = doc.get("text", "")
        source = doc.get("source", "")
        url = doc.get("url", "")
        for chunk in chunk_text(text, chunk_size=chunk_size, overlap=overlap):
            ids.append(_chunk_id(source, chunk))
            texts.append(chunk)
            metadatas.append({"source": source, "url": url})

    if not texts:
        print("Uyarı: İndekslenecek boş olmayan metin bulunamadı.")
        return 0

    print(f"{len(texts)} chunk embedding'e çevriliyor...")
    embeddings = model.encode(texts, show_progress_bar=False).tolist()
    collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
    print(f"İndeks tamamlandı: {len(texts)} chunk '{collection_name}' koleksiyonuna yazıldı.")
    return len(texts)
