from openai import OpenAI

from app.core.config import settings


class OpenAICompatibleEmbeddings:
    def __init__(self) -> None:
        if not settings.openai_api_key.strip():
            raise RuntimeError("OPENAI_API_KEY is required to build or query the RAG index")

        client_kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url.strip():
            client_kwargs["base_url"] = settings.openai_base_url.strip()
        self.client = OpenAI(**client_kwargs)
        self.model = settings.embedding_model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]
