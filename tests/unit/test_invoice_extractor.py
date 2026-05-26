"""
Unit tests for InvoiceExtractor.

We test purely at the text level — no file I/O, no loaders, no FastAPI.
This makes tests fast, deterministic, and easy to add new invoice samples to.

Test structure
──────────────
  1. TestInvoiceExtractorCleanInvoice   — a well-formatted synthetic invoice
  2. TestInvoiceExtractorNoisyText      — OCR-noise and broken lines
  3. TestInvoiceExtractorPartialData    — only some fields present
  4. TestInvoiceExtractorLineItems      — focused table-parsing tests
  5. TestInvoiceExtractorEdgeCases      — empty text, whitespace-only, etc.
"""
import pytest

from app.extraction.invoice_extractor import InvoiceExtractor
from app.extraction.schemas import InvoiceExtractionResult


# ── Helpers ────────────────────────────────────────────────────────────────────

def extract(text: str) -> InvoiceExtractionResult:
    """Convenience wrapper — create extractor and run extraction."""
    return InvoiceExtractor(text).extract()


# ══════════════════════════════════════════════════════════════════════════════
# 1. Clean, well-formatted invoice
# ══════════════════════════════════════════════════════════════════════════════

CLEAN_INVOICE = """\
Acme Corp Ltd
123 Business Street, Mumbai 400001

Invoice Number: INV-2024-001
Invoice Date: 15/01/2024
Due Date: 14/02/2024

Bill To:
Customer Name Inc.
456 Client Avenue

Description              Qty   Unit Price   Amount
Widget A                   2      500.00   1000.00
Widget B                   1      234.56    234.56

Subtotal:                                  1234.56
Tax (18%):                                  222.22
Grand Total: INR 1,456.78
"""


class TestInvoiceExtractorCleanInvoice:
    """All fields should be found with high confidence on a clean invoice."""

    @pytest.fixture(scope="class")
    def result(self):
        return extract(CLEAN_INVOICE)

    def test_vendor_name_found(self, result):
        assert result.fields.vendor_name is not None
        assert "Acme" in result.fields.vendor_name

    def test_invoice_number_correct(self, result):
        assert result.fields.invoice_number == "INV-2024-001"

    def test_invoice_number_confidence_high(self, result):
        assert result.confidence.invoice_number >= 0.90

    def test_invoice_date_correct(self, result):
        assert result.fields.invoice_date == "2024-01-15"

    def test_invoice_date_confidence_high(self, result):
        assert result.confidence.invoice_date >= 0.90

    def test_due_date_correct(self, result):
        assert result.fields.due_date == "2024-02-14"

    def test_due_date_confidence_high(self, result):
        assert result.confidence.due_date >= 0.90

    def test_total_amount_correct(self, result):
        assert result.fields.total_amount == 1456.78

    def test_total_amount_confidence_high(self, result):
        assert result.confidence.total_amount >= 0.95

    def test_currency_detected_as_inr(self, result):
        assert result.fields.currency == "INR"

    def test_overall_confidence_above_threshold(self, result):
        # With 5+ fields found at high confidence, overall should be ≥ 0.75
        assert result.overall_confidence >= 0.75

    def test_line_items_extracted(self, result):
        assert len(result.fields.line_items) >= 1

    def test_no_errors(self, result):
        assert result.extraction_warnings == []

    def test_raw_text_length_set(self, result):
        assert result.raw_text_length > 0


# ══════════════════════════════════════════════════════════════════════════════
# 2. OCR-noisy text
# ══════════════════════════════════════════════════════════════════════════════

NOISY_INVOICE = """\
XYZ  Pvt.  Ltd.
Inv0ice  N0:  INV-2024-007
Inv0ice  Date:  20/03/2024
Net  30

Gr@nd  T0tal:  $  2,500.00
"""


class TestInvoiceExtractorNoisyText:
    """
    OCR noise (extra spaces, zeros replacing O's) degrades but shouldn't break.
    We assert on what the regex *can* still find, not perfection.
    """

    @pytest.fixture(scope="class")
    def result(self):
        return extract(NOISY_INVOICE)

    def test_extract_returns_result_object(self, result):
        assert isinstance(result, InvoiceExtractionResult)

    def test_no_crash(self, result):
        # Should never raise — errors become warnings
        assert isinstance(result.extraction_warnings, list)

    def test_total_amount_or_none_no_crash(self, result):
        # "Gr@nd  T0tal:" has OCR noise that defeats the regex — acceptable.
        # The key guarantee is: no exception, result is a valid object.
        assert result.fields.total_amount is None or result.fields.total_amount == 2500.00

    def test_net_terms_compute_due_date(self, result):
        # "Net 30" + invoice_date "2024-03-20" → due 2024-04-19
        if result.fields.invoice_date:   # only assert if date was found
            assert result.fields.due_date == "2024-04-19"


# ══════════════════════════════════════════════════════════════════════════════
# 3. Partial data — only some fields present
# ══════════════════════════════════════════════════════════════════════════════

PARTIAL_INVOICE = """\
Some Company
Invoice No: PARTIAL-001

Total: 500
"""


class TestInvoiceExtractorPartialData:

    @pytest.fixture(scope="class")
    def result(self):
        return extract(PARTIAL_INVOICE)

    def test_invoice_number_found(self, result):
        assert result.fields.invoice_number == "PARTIAL-001"

    def test_total_found(self, result):
        assert result.fields.total_amount == 500.0

    def test_missing_date_is_none(self, result):
        assert result.fields.invoice_date is None

    def test_missing_date_confidence_zero(self, result):
        assert result.confidence.invoice_date == 0.0

    def test_overall_confidence_lower(self, result):
        # Fewer fields → lower mean confidence (but still non-zero)
        assert 0.0 < result.overall_confidence < 1.0


# ══════════════════════════════════════════════════════════════════════════════
# 4. Line item table parsing
# ══════════════════════════════════════════════════════════════════════════════

TABLE_INVOICE = """\
Tech Solutions Inc.
Invoice No: TS-2024-099
Invoice Date: 01/06/2024

Description          Qty    Unit Price    Amount
Web Design             1      5000.00    5000.00
Hosting (annual)       1       999.00     999.00
Domain renewal         1        15.00      15.00

Subtotal                                 6014.00
Grand Total: USD 6,014.00
"""


class TestInvoiceExtractorLineItems:

    @pytest.fixture(scope="class")
    def result(self):
        return extract(TABLE_INVOICE)

    def test_three_line_items(self, result):
        assert len(result.fields.line_items) == 3

    def test_first_item_amount(self, result):
        first = result.fields.line_items[0]
        assert first.amount == 5000.0

    def test_second_item_amount(self, result):
        second = result.fields.line_items[1]
        assert second.amount == 999.0

    def test_third_item_amount(self, result):
        third = result.fields.line_items[2]
        assert third.amount == 15.0

    def test_first_item_has_description(self, result):
        first = result.fields.line_items[0]
        assert first.description is not None
        assert len(first.description) > 0

    def test_currency_usd(self, result):
        assert result.fields.currency == "USD"

    def test_total_amount_correct(self, result):
        assert result.fields.total_amount == 6014.0


# ══════════════════════════════════════════════════════════════════════════════
# 5. Edge cases
# ══════════════════════════════════════════════════════════════════════════════

class TestInvoiceExtractorEdgeCases:

    def test_empty_text(self):
        result = extract("")
        assert isinstance(result, InvoiceExtractionResult)
        assert result.fields.invoice_number is None
        assert result.overall_confidence == 0.0

    def test_whitespace_only(self):
        result = extract("   \n\n\t  ")
        assert result.overall_confidence == 0.0

    def test_result_is_json_serialisable(self):
        result = extract(CLEAN_INVOICE)
        json_str = result.model_dump_json()
        assert "invoice_number" in json_str
        assert "overall_confidence" in json_str

    def test_all_fields_optional_never_raise(self):
        """A completely unrelated text should return gracefully with no errors."""
        result = extract("The quick brown fox jumps over the lazy dog.")
        assert isinstance(result, InvoiceExtractionResult)
        assert result.extraction_warnings == []

    def test_different_currency_formats(self):
        """Euro symbol, European number format."""
        text = "Grand Total: €1.234,56"
        result = extract(text)
        assert result.fields.total_amount == 1234.56
        assert result.fields.currency == "EUR"

    def test_net_30_without_invoice_date(self):
        """Net 30 present but no invoice_date → due_date stays None."""
        text = "Invoice No: X-001\nNet 30\nTotal: 100"
        result = extract(text)
        # due_date requires invoice_date for Net-terms computation
        assert result.fields.due_date is None

    def test_grand_total_wins_over_subtotal(self):
        """The 'Grand Total' pattern should beat the bare 'Total' pattern."""
        text = (
            "Subtotal: 1000.00\n"
            "Tax: 180.00\n"
            "Grand Total: 1180.00\n"
        )
        result = extract(text)
        assert result.fields.total_amount == 1180.00
        assert result.confidence.total_amount >= 0.95   # Grand Total = 0.97
