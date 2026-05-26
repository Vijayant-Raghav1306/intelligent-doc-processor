"""
Abstract base class for all document extractors.

Mirrors the BaseLoader pattern from services/base_loader.py:
  - Constructor accepts raw text (not a file — loaders handle files)
  - extract() is the single required method
  - clean_text is available to all subclasses via the property

To implement a new extractor (e.g. ResumeExtractor):
  1. Inherit BaseExtractor
  2. Implement extract() → return a Pydantic result model
  3. Register an endpoint in api/routes/extraction.py
"""
from abc import ABC, abstractmethod

from app.extraction.normalizers import clean_text


class BaseExtractor(ABC):
    """
    Base class all extractors must extend.

    Args:
        text: Raw text produced by a loader (pdf_loader, image_loader, docx_loader).
              May contain OCR noise, irregular whitespace, and broken lines.
    """

    def __init__(self, text: str) -> None:
        self.raw_text   = text
        self.clean_text = clean_text(text)   # pre-cleaned, available to all subclasses

    @abstractmethod
    def extract(self):
        """
        Run extraction and return a typed result model.

        Must be implemented by every subclass.
        Must not raise — catch internal errors and surface them as warnings
        in the result's extraction_warnings list.
        """
        ...
