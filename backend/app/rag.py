import hashlib
import re
from functools import lru_cache
from typing import Any
from uuid import uuid4

import httpx

from .config import Settings


def chunk_text(text: str, max_words: int = 180, overlap: int = 35) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    words = cleaned.split()
    if not words:
        return []
    chunks: list[str] = []
    step = max_words - overlap
    for start in range(0, len(words), step):
        chunk = " ".join(words[start:start + max_words]).strip()
        if chunk:
            chunks.append(chunk)
        if start + max_words >= len(words):
            break
    return chunks


@lru_cache
def get_embedding_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def embed_texts(texts: list[str], settings: Settings) -> list[list[float]]:
    model = get_embedding_model(settings.embedding_model)
    vectors = model.encode(texts, normalize_embeddings=True)
    return [vector.tolist() for vector in vectors]


async def ensure_collection(settings: Settings, vector_size: int) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{settings.qdrant_url}/collections/{settings.qdrant_collection}"
        )
        if response.status_code == 200:
            return
        if response.status_code != 404:
            raise RuntimeError(f"Qdrant collection check failed: {response.text}")
        create = await client.put(
            f"{settings.qdrant_url}/collections/{settings.qdrant_collection}",
            json={
                "vectors": {
                    "size": vector_size,
                    "distance": "Cosine",
                }
            },
        )
        if create.is_error:
            raise RuntimeError(f"Qdrant collection create failed: {create.text}")


async def ingest_text(title: str, text: str, source_type: str, settings: Settings) -> int:
    chunks = chunk_text(text)
    if not chunks:
        return 0

    vectors = embed_texts(chunks, settings)
    await ensure_collection(settings, len(vectors[0]))
    source_id = hashlib.sha1(f"{title}:{source_type}:{text}".encode("utf-8")).hexdigest()
    points = []
    for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
        points.append(
            {
                "id": str(uuid4()),
                "vector": vector,
                "payload": {
                    "source_id": source_id,
                    "title": title,
                    "source_type": source_type,
                    "chunk_index": idx,
                    "text": chunk,
                },
            }
        )

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.put(
            f"{settings.qdrant_url}/collections/{settings.qdrant_collection}/points",
            json={"points": points},
        )
        if response.is_error:
            raise RuntimeError(f"Qdrant upsert failed: {response.text}")
    return len(points)


async def retrieve_context(query: str, settings: Settings) -> str:
    if not settings.rag_enabled:
        return ""
    try:
        vectors = embed_texts([query], settings)
        await ensure_collection(settings, len(vectors[0]))
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.qdrant_url}/collections/{settings.qdrant_collection}/points/search",
                json={
                    "vector": vectors[0],
                    "limit": settings.rag_top_k,
                    "with_payload": True,
                    "score_threshold": 0.25,
                },
            )
            if response.is_error:
                return ""
            results = response.json().get("result", [])
    except Exception:
        return ""

    snippets = []
    for item in results:
        payload = item.get("payload", {})
        text = payload.get("text")
        title = payload.get("title", "knowledge")
        if text:
            snippets.append(f"[{title}] {text}")
    return "\n\n".join(snippets)


async def list_knowledge(settings: Settings) -> list[dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.qdrant_url}/collections/{settings.qdrant_collection}/points/scroll",
                json={"limit": 100, "with_payload": True, "with_vector": False},
            )
            if response.is_error:
                return []
            points = response.json().get("result", {}).get("points", [])
    except Exception:
        return []

    seen: dict[str, dict[str, Any]] = {}
    for point in points:
        payload = point.get("payload", {})
        source_id = payload.get("source_id", point.get("id"))
        if source_id in seen:
            continue
        text = payload.get("text", "")
        seen[source_id] = {
            "id": source_id,
            "title": payload.get("title", "knowledge"),
            "source_type": payload.get("source_type", "profile"),
            "preview": text[:180],
        }
    return list(seen.values())
