from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class ModelPurpose(StrEnum):
    preparation = "preparation"
    chat = "chat"
    minutes = "minutes"
    extraction = "extraction"


class PurposeModelsWrite(BaseModel):
    models: dict[ModelPurpose, str] = Field(default_factory=dict)

    @field_validator("models")
    @classmethod
    def _validate_models(cls, value: dict[ModelPurpose, str]) -> dict[ModelPurpose, str]:
        cleaned: dict[ModelPurpose, str] = {}
        for purpose, model in value.items():
            text = model.strip()
            if not text:
                raise ValueError("用途模型名不能为空")
            if len(text) > 100:
                raise ValueError("用途模型名不能超过 100 个字符")
            cleaned[purpose] = text
        return cleaned


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
    llm_purpose_models: dict[str, str]
    embedding_api_base: str
    embedding_model: str
    embedding_api_key_masked: str
    embedding_source: str
    embedding_dim: int


class ModelConfigDeleteResult(BaseModel):
    deleted: bool = True
