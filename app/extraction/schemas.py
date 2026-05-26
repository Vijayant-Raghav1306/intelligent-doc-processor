"""
Pydantic schemas for all extraction results.

Design rules:
  - Every extracted field is Optional — extraction may fail gracefully.
  - Every field has a parallel confidence score (0.0 to 1.0).
  - Dates are always returned as ISO 8601 strings (YYYY-MM-DD).
  - Amounts are always returned as Python floats.
  - Currency is always returned as ISO 4217 three-letter codes (USD, EUR, INR).
  - overall_confidence is the mean of all non-zero field confidences.

To add a new document type (receipt, contract, resume):
  - Add a new Fields model (e.g. ReceiptFields)
  - Add a new Confidence model
  - Add a new Result model
  - Write a new extractor extending BaseExtractor
"""
from typing import Optional

from pydantic import BaseModel, Field, computed_field


# ── Sub-models ────────────────────────────────────────────────────────────────

class LineItem(BaseModel):
    """A single line item on an invoice."""
    description: Optional[str]   = None
    quantity:    Optional[float] = None
    unit_price:  Optional[float] = None
    amount:      Optional[float] = None


class InvoiceFields(BaseModel):
    """The structured fields we attempt to extract from an invoice."""
    vendor_name:    Optional[str]   = None   # company that issued the invoice
    invoice_number: Optional[str]   = None   # unique identifier e.g. INV-2024-001
    invoice_date:   Optional[str]   = None   # ISO 8601: YYYY-MM-DD
    due_date:       Optional[str]   = None   # ISO 8601: YYYY-MM-DD
    total_amount:   Optional[float] = None   # final payable amount as float
    currency:       Optional[str]   = None   # ISO 4217: USD, EUR, INR ...
    line_items:     list[LineItem]  = []


class FieldConfidence(BaseModel):
    """
    Per-field confidence scores: 0.0 (not found) to 1.0 (certain match).

    Confidence thresholds used throughout the extractor:
      >= 0.85  strong labeled match       "Invoice Number: INV-001"
      >= 0.65  labeled but less specific  "No: INV-001"
      >= 0.40  unlabeled heuristic        first date found in document
       0.0     field not found at all
    """
    vendor_name:    float = Field(0.0, ge=0.0, le=1.0)
    invoice_number: float = Field(0.0, ge=0.0, le=1.0)
    invoice_date:   float = Field(0.0, ge=0.0, le=1.0)
    due_date:       float = Field(0.0, ge=0.0, le=1.0)
    total_amount:   float = Field(0.0, ge=0.0, le=1.0)
    currency:       float = Field(0.0, ge=0.0, le=1.0)


# ── Top-level result ──────────────────────────────────────────────────────────

class InvoiceExtractionResult(BaseModel):
    """
    Complete result returned by InvoiceExtractor.extract().
    This is the shape the API returns to the caller.
    """
    document_type:       str             = "invoice"
    fields:              InvoiceFields   = Field(default_factory=InvoiceFields)
    confidence:          FieldConfidence = Field(default_factory=FieldConfidence)
    extraction_warnings: list[str]       = []
    raw_text_length:     int             = 0

    @computed_field
    @property
    def overall_confidence(self) -> float:
        """Mean of all non-zero field confidence scores. 0.0 if nothing found."""
        scores = [v for v in self.confidence.model_dump().values() if v > 0.0]
        return round(sum(scores) / len(scores), 2) if scores else 0.0
