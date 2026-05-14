from dataclasses import dataclass

from app.rag.loader import LoadedDocument


@dataclass(frozen=True)
class TextChunk:
    id: str
    source: str
    file_name: str
    chunk_index: int
    content: str


def split_documents(
    documents: list[LoadedDocument],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []

    for document_index, document in enumerate(documents):
        paragraphs = [item.strip() for item in document.content.split("\n\n") if item.strip()]
        current = ""
        chunk_index = 0

        for paragraph in paragraphs:
            candidate = paragraph if not current else f"{current}\n\n{paragraph}"
            if len(candidate) <= chunk_size:
                current = candidate
                continue

            if current:
                chunks.append(_build_chunk(document, document_index, chunk_index, current))
                chunk_index += 1
                overlap_text = current[-chunk_overlap:] if chunk_overlap > 0 else ""
                current = f"{overlap_text}\n\n{paragraph}" if overlap_text else paragraph
            else:
                for start in range(0, len(paragraph), max(1, chunk_size - chunk_overlap)):
                    part = paragraph[start:start + chunk_size]
                    chunks.append(_build_chunk(document, document_index, chunk_index, part))
                    chunk_index += 1
                current = ""

        if current:
            chunks.append(_build_chunk(document, document_index, chunk_index, current))

    return chunks


def _build_chunk(
    document: LoadedDocument,
    document_index: int,
    chunk_index: int,
    content: str,
) -> TextChunk:
    chunk_id = f"doc-{document_index}-chunk-{chunk_index}"
    return TextChunk(
        id=chunk_id,
        source=document.source,
        file_name=document.file_name,
        chunk_index=chunk_index,
        content=f"{document.file_name}\n{content}",
    )
