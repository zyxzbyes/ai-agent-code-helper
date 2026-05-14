from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://localhost:8081",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    model_name: str = Field(default="qwen-plus", alias="MODEL_NAME")
    temperature: float = Field(default=0.7, alias="TEMPERATURE")
    max_memory_messages: int = Field(default=10, alias="MAX_MEMORY_MESSAGES")
    database_url: str = Field(default="sqlite:///./data/app.db", alias="DATABASE_URL")
    jwt_secret_key: str = Field(default="change-this-jwt-secret-key-min-32-bytes", alias="JWT_SECRET_KEY")
    jwt_expire_minutes: int = Field(default=10080, alias="JWT_EXPIRE_MINUTES")
    rag_enabled: bool = Field(default=True, alias="RAG_ENABLED")
    rag_docs_dir: str = Field(default="./data/docs", alias="RAG_DOCS_DIR")
    rag_index_dir: str = Field(default="./data/vector_index", alias="RAG_INDEX_DIR")
    rag_chunk_size: int = Field(default=1000, alias="RAG_CHUNK_SIZE")
    rag_chunk_overlap: int = Field(default=200, alias="RAG_CHUNK_OVERLAP")
    rag_top_k: int = Field(default=5, alias="RAG_TOP_K")
    rag_score_threshold: float = Field(default=0.75, alias="RAG_SCORE_THRESHOLD")
    embedding_model: str = Field(default="text-embedding-v4", alias="EMBEDDING_MODEL")
    web_search_enabled: bool = Field(default=True, alias="WEB_SEARCH_ENABLED")
    bigmodel_api_key: str = Field(default="", alias="BIGMODEL_API_KEY")
    mcp_web_search_url: str = Field(
        default="https://open.bigmodel.cn/api/mcp/web_search_prime/mcp",
        alias="MCP_WEB_SEARCH_URL",
    )
    web_search_top_k: int = Field(default=5, alias="WEB_SEARCH_TOP_K")
    guardrail_enabled: bool = Field(default=True, alias="GUARDRAIL_ENABLED")
    cors_origins: str = Field(
        default=",".join(DEFAULT_CORS_ORIGINS),
        alias="CORS_ORIGINS",
    )

    @field_validator("max_memory_messages")
    @classmethod
    def validate_max_memory_messages(cls, value: int) -> int:
        if value < 0:
            raise ValueError("MAX_MEMORY_MESSAGES must be greater than or equal to 0")
        return value

    @field_validator("jwt_expire_minutes")
    @classmethod
    def validate_jwt_expire_minutes(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("JWT_EXPIRE_MINUTES must be greater than 0")
        return value

    @field_validator("rag_chunk_size", "rag_top_k", "web_search_top_k")
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("RAG_CHUNK_SIZE, RAG_TOP_K and WEB_SEARCH_TOP_K must be greater than 0")
        return value

    @field_validator("rag_chunk_overlap")
    @classmethod
    def validate_chunk_overlap(cls, value: int) -> int:
        if value < 0:
            raise ValueError("RAG_CHUNK_OVERLAP must be greater than or equal to 0")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins.strip():
            return DEFAULT_CORS_ORIGINS.copy()
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
