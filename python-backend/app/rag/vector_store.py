from pathlib import Path

import chromadb

from app.core.config import settings
from app.rag.splitter import TextChunk


COLLECTION_NAME = "ai_code_helper_docs"


def get_client():
    Path(settings.rag_index_dir).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=settings.rag_index_dir)


def get_collection():
    client = get_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def reset_collection():
    client = get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    return client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(chunks: list[TextChunk], embeddings: list[list[float]]) -> None:
    if not chunks:
        return

    collection = get_collection()
    collection.add(
        ids=[chunk.id for chunk in chunks],
        documents=[chunk.content for chunk in chunks],
        embeddings=embeddings,
        metadatas=[
            {
                "source": chunk.source,
                "file_name": chunk.file_name,
                "chunk_index": chunk.chunk_index,
            }
            for chunk in chunks
        ],
    )
