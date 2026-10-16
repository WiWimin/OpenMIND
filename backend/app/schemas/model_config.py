from __future__ import annotations

from pydantic import BaseModel


class ModelConfigWrite(BaseModel):
    llm_api_base: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    embedding_api_base: str | None = None
    embedding_api_key: str | None = None
    embedding_model: str | None = None


class ModelConfigRead(BaseModel):
    llm_api_base: str
    llm_model: str
    llm_api_key_masked: str
    llm_source: str
    embedding_api_base: str
    embedding_model: str
    embedding_api_key_masked: str
    embedding_source: str
    embedding_dim: int


class ModelConfigDeleteResult(BaseModel):
    deleted: bool = True
