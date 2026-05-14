from dataclasses import dataclass

from app.core.config import settings
from app.rag.embeddings import OpenAICompatibleEmbeddings
from app.rag.vector_store import get_collection


@dataclass(frozen=True)
class RetrievedChunk:
    source: str
    file_name: str
    chunk_index: int
    score: float
    content: str


def retrieve(query: str) -> list[RetrievedChunk]:
    if not settings.rag_enabled or not query.strip():
        return []

    embeddings = OpenAICompatibleEmbeddings()
    query_embedding = embeddings.embed_query(query)
    collection = get_collection()
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=settings.rag_top_k,
        include=["documents", "metadatas", "distances"],
    )

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    chunks: list[RetrievedChunk] = []

    for document, metadata, distance in zip(documents, metadatas, distances):
        score = 1 - float(distance)
        if score < settings.rag_score_threshold:
            continue
        chunks.append(
            RetrievedChunk(
                source=str(metadata.get("source", "")),
                file_name=str(metadata.get("file_name", "")),
                chunk_index=int(metadata.get("chunk_index", 0)),
                score=score,
                content=document,
            )
        )
    return chunks


def format_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return ""

    parts = []
    for index, chunk in enumerate(chunks, start=1):
        parts.append(
            f"[{index}] 来源：{chunk.file_name}#chunk-{chunk.chunk_index}，相关度：{chunk.score:.4f}\n{chunk.content}"
        )
    return "\n\n---\n\n".join(parts)
