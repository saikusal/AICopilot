from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Interview Copilot"
    cors_origins: str = "*"

    deepgram_api_key: str | None = None
    deepgram_model: str = "nova-3"
    stt_provider: str = "deepgram"
    whisper_model: str = "small.en"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"

    llm_provider: str = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.2"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    answer_max_tokens: int = 650
    auto_pause_seconds: int = 15

    class Config:
        env_file = (".env", "../.env")
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
