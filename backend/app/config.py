from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_port: int = 8080
    max_file_size_mb: int = 100
    max_pages: int = 200
    document_retention_minutes: int = 60
    ocr_language: str = "deu+eng"
    ocr_dpi: int = 200
    ocr_timeout_seconds: int = 90
    processing_timeout_seconds: int = 1800
    max_concurrent_jobs: int = 3
    max_render_pixels: int = 50_000_000
    page_render_timeout_seconds: int = 60
    enable_api_docs: bool = False
    llm_enabled: bool = False
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen3:1.7b"
    admin_token: str = ""
    stats_file: str = "/data/stats.json"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
