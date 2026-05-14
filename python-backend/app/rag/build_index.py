from app.core.config import settings
from app.rag.embeddings import OpenAICompatibleEmbeddings
from app.rag.loader import load_documents
from app.rag.splitter import split_documents
from app.rag.vector_store import add_chunks, reset_collection


def build_index() -> None:
    documents = load_documents(settings.rag_docs_dir)
    chunks = split_documents(
        documents,
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
    )
    reset_collection()

    if not chunks:
        print(f"No documents found in {settings.rag_docs_dir}")
        return

    embeddings = OpenAICompatibleEmbeddings()
    batch_size = 10
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        vectors = embeddings.embed_texts([chunk.content for chunk in batch])
        add_chunks(batch, vectors)
        print(f"Indexed {min(start + batch_size, len(chunks))}/{len(chunks)} chunks")

    print(
        f"RAG index built: {len(documents)} documents, {len(chunks)} chunks, "
        f"persisted at {settings.rag_index_dir}"
    )


if __name__ == "__main__":
    build_index()
