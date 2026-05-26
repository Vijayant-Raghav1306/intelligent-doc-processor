from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Intelligent Doc Processor"

    # File size limit — stored in MB for human readability
    max_file_size_mb: int = 10

    # Directories — relative to where you run the server from
    upload_dir: str = "uploads"
    output_dir: str = "outputs"

    # MIME types we actually handle — detected from file bytes, not extension
    allowed_mime_types: list[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/tiff",
        "image/webp",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]

    # Tesseract binary path.
    #   Linux / Render:  "tesseract"  (installed via apt-get, lives on PATH)
    #   macOS:           "tesseract"  (installed via brew)
    #   Windows:         full path, e.g. r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    # Override with TESSERACT_CMD= in your .env file.
    tesseract_cmd: str = "tesseract"

    # spaCy model name — upgrade to en_core_web_md/lg/trf for better accuracy.
    # Set SPACY_MODEL=en_core_web_trf in .env for transformer-based NER.
    # Set SPACY_MODEL="" (empty string) to disable NLP and use regex-only mode.
    spacy_model: str = "en_core_web_sm"

    # CORS allowed origins — comma-separated list of frontend URLs.
    # Default "*" allows all origins (fine while allow_credentials=False).
    # In production set: CORS_ORIGINS=https://your-app.vercel.app
    cors_origins: str = "*"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)


# Single instance — import this object everywhere, never instantiate Settings() yourself
settings = Settings()
