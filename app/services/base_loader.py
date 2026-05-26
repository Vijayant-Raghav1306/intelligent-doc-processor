from abc import ABC, abstractmethod
from pathlib import Path

from PIL import Image


class BaseLoader(ABC):
    """
    Contract that every document loader must follow.
    Inherit this class and implement all three abstract methods.
    """

    def __init__(self, file_path: str | Path):
        # Normalize to Path object so all loaders work identically on any OS
        self.file_path = Path(file_path)
        self.validate_file_exists()

    # ── Shared behaviour (concrete — runs as-is for every subclass) ───────────

    def validate_file_exists(self) -> None:
        """Raises immediately if the file is missing — fail fast, fail loud."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

    def get_file_size_bytes(self) -> int:
        """File size in bytes — available to all loaders without reimplementing."""
        return self.file_path.stat().st_size

    # ── Contract (abstract — every subclass MUST implement these) ─────────────

    @abstractmethod
    def extract_text(self) -> str:
        """
        Extract and return all text from the document as a single string.
        Multi-page documents should concatenate pages with newlines.
        """
        ...

    @abstractmethod
    def get_preview_image(self) -> Image.Image:
        """
        Render the first page of the document as a PIL Image.
        Caller is responsible for saving/encoding the returned image.
        """
        ...

    @abstractmethod
    def get_metadata(self) -> dict:
        """
        Return a dict with at minimum:
          { "page_count": int, "file_type": str, "file_size_bytes": int }
        Loaders may add format-specific keys (e.g. "author", "is_encrypted").
        """
        ...
