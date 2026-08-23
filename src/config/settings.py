from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMES_PATH = Path(__file__).resolve().parent / "schemes.yaml"

ALLOWED_SOURCE_DOMAINS: tuple[str, ...] = ("groww.in",)
REFUSAL_CITATION_URL = "https://groww.in/p/mutual-funds"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_model_fast: str = "qwen/qwen3.6-27b"
    groq_max_tokens: int = 256
    groq_generation_max_tokens: int = 128
    groq_temperature: float = 0.1

    # openai/gpt-oss-120b quotas (Groq console defaults)
    groq_rpm: int = 30
    groq_rpd: int = 1000
    groq_tpm: int = 8000
    groq_tpd: int = 200_000
    groq_rate_limit_max_wait: float = 65.0

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    raw_data_dir: Path = Field(default=PROJECT_ROOT / "data" / "raw")
    processed_data_dir: Path = Field(default=PROJECT_ROOT / "data" / "processed")
    chroma_persist_dir: Path = Field(default=PROJECT_ROOT / "data" / "index")

    allowed_source_domains: tuple[str, ...] = ALLOWED_SOURCE_DOMAINS
    refusal_citation_url: str = REFUSAL_CITATION_URL

    @property
    def schemes_path(self) -> Path:
        return SCHEMES_PATH


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def load_schemes() -> list[dict]:
    """Load scheme registry from YAML."""
    with open(SCHEMES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("schemes", [])
