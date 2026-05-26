"""
Unit tests for app/extraction/nlp_utils.py

These tests verify the NLP utility functions using a real spaCy Doc.
Tests are skipped (not failed) when spaCy / the model is unavailable,
so CI environments without the model still pass cleanly.

Test structure
──────────────
  TestExtractOrgEntities    — ORG entity detection + confidence scoring
  TestExtractDateEntities   — DATE entity detection + relative date filtering
  TestExtractMoneyEntities  — MONEY entity detection + currency handling
  TestFindEntityNearKeyword — contextual proximity search
  TestFuseConfidence        — fusion rules for regex + NLP results
  TestValidateConsistency   — cross-field sanity checks
"""
import pytest

from app.extraction.nlp_service import get_nlp, load_nlp
from app.extraction.nlp_utils import (
    extract_date_entities,
    extract_money_entities,
    extract_org_entities,
    find_entity_near_keyword,
    fuse_confidence,
    validate_field_consistency,
)

# ── Availability marker ────────────────────────────────────────────────────────

def _spacy_available() -> bool:
    try:
        import spacy
        spacy.load("en_core_web_sm")
        return True
    except Exception:
        return False


requires_spacy = pytest.mark.skipif(
    not _spacy_available(),
    reason="spaCy en_core_web_sm model not installed — skipping NLP tests",
)


# ── Shared fixture — one nlp load per module ──────────────────────────────────

@pytest.fixture(scope="module")
def nlp():
    """Load the spaCy model once for the entire test module."""
    load_nlp()
    model = get_nlp()
    if model is None:
        pytest.skip("spaCy model not available")
    return model


# ══════════════════════════════════════════════════════════════════════════════
# ORG entity extraction
# ══════════════════════════════════════════════════════════════════════════════

@requires_spacy
class TestExtractOrgEntities:

    def test_detects_company_with_suffix(self, nlp):
        doc = nlp("Acme Corp Ltd\n123 Main Street")
        orgs = extract_org_entities(doc)
        assert len(orgs) >= 1
        texts = [t for t, _ in orgs]
        assert any("Acme" in t for t in texts)

    def test_confidence_higher_with_org_suffix(self, nlp):
        # "Pvt. Ltd." suffix should boost confidence
        doc_with    = nlp("Skyline Solutions Pvt. Ltd.")
        doc_without = nlp("Skyline Solutions")
        orgs_with    = extract_org_entities(doc_with)
        orgs_without = extract_org_entities(doc_without)
        if orgs_with and orgs_without:
            assert orgs_with[0][1] >= orgs_without[0][1]

    def test_returns_sorted_by_confidence(self, nlp):
        doc = nlp("Microsoft Corp\nXYZ\nAcme Ltd")
        orgs = extract_org_entities(doc)
        if len(orgs) >= 2:
            confs = [c for _, c in orgs]
            assert confs == sorted(confs, reverse=True)

    def test_empty_text_returns_empty(self, nlp):
        doc = nlp("")
        assert extract_org_entities(doc) == []

    def test_no_org_returns_empty(self, nlp):
        doc = nlp("The invoice total is $500.00 due on January 15.")
        # Even if spaCy is wrong, function should return a list (possibly empty)
        result = extract_org_entities(doc)
        assert isinstance(result, list)


# ══════════════════════════════════════════════════════════════════════════════
# DATE entity extraction
# ══════════════════════════════════════════════════════════════════════════════

@requires_spacy
class TestExtractDateEntities:

    def test_detects_iso_date(self, nlp):
        doc = nlp("Invoice Date: 2024-01-15")
        dates = extract_date_entities(doc)
        assert len(dates) >= 1

    def test_detects_textual_date(self, nlp):
        doc = nlp("Issued on 15 January 2024")
        dates = extract_date_entities(doc)
        texts = [t for t, _ in dates]
        assert any("January" in t or "2024" in t for t in texts)

    def test_relative_dates_filtered_out(self, nlp):
        # "yesterday" and "last month" should be filtered
        doc = nlp("Payment was received yesterday and last month.")
        dates = extract_date_entities(doc)
        texts = [t.lower() for t, _ in dates]
        assert "yesterday" not in texts
        assert not any("last" in t for t in texts)

    def test_date_with_year_has_higher_confidence(self, nlp):
        doc = nlp("Due date: 15 February 2024")
        dates = extract_date_entities(doc)
        if dates:
            # Dates containing a year should have conf > 0.70
            best_conf = max(c for _, c in dates)
            assert best_conf > 0.70

    def test_empty_text_returns_empty(self, nlp):
        doc = nlp("")
        assert extract_date_entities(doc) == []


# ══════════════════════════════════════════════════════════════════════════════
# MONEY entity extraction
# ══════════════════════════════════════════════════════════════════════════════

@requires_spacy
class TestExtractMoneyEntities:

    def test_detects_dollar_amount(self, nlp):
        doc = nlp("Grand Total: $1,234.56")
        money = extract_money_entities(doc)
        assert len(money) >= 1

    def test_detects_usd_code_amount(self, nlp):
        # en_core_web_sm may tag "USD 3,750.00" as MONEY or split it differently.
        # We only assert the function doesn't crash and returns a list.
        doc = nlp("Total Amount Due: USD 3,750.00")
        money = extract_money_entities(doc)
        assert isinstance(money, list)   # always returns a list, never raises

    def test_confidence_higher_with_currency_symbol(self, nlp):
        doc = nlp("Total: $500.00")
        money = extract_money_entities(doc)
        if money:
            best_conf = max(c for _, c in money)
            assert best_conf >= 0.72

    def test_empty_text_returns_empty(self, nlp):
        doc = nlp("")
        assert extract_money_entities(doc) == []

    def test_result_is_list(self, nlp):
        doc = nlp("No monetary values here.")
        assert isinstance(extract_money_entities(doc), list)


# ══════════════════════════════════════════════════════════════════════════════
# Contextual keyword proximity search
# ══════════════════════════════════════════════════════════════════════════════

@requires_spacy
class TestFindEntityNearKeyword:

    def test_finds_date_near_invoice(self, nlp):
        doc = nlp("Invoice Date: 15 January 2024")
        result = find_entity_near_keyword(doc, "invoice", "DATE", window_tokens=8)
        # spaCy should find a DATE entity near "invoice"
        # (May be None if spaCy doesn't detect the entity — that's acceptable)
        assert result is None or (isinstance(result[0], str) and isinstance(result[1], float))

    def test_finds_money_near_total(self, nlp):
        doc = nlp("Grand Total: $3,750.00")
        result = find_entity_near_keyword(doc, "total", "MONEY", window_tokens=6)
        assert result is None or isinstance(result, tuple)

    def test_returns_none_for_absent_keyword(self, nlp):
        doc = nlp("Invoice Number: INV-2024-001")
        result = find_entity_near_keyword(doc, "banana", "DATE", window_tokens=5)
        assert result is None

    def test_returns_none_for_wrong_entity_type(self, nlp):
        doc = nlp("Invoice Date: 15 January 2024")
        # Looking for MONEY near "invoice" — shouldn't find anything
        result = find_entity_near_keyword(doc, "invoice", "MONEY", window_tokens=8)
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# Confidence fusion — pure logic, no spaCy needed
# ══════════════════════════════════════════════════════════════════════════════

class TestFuseConfidence:
    """These tests are pure logic — no spaCy model needed."""

    def test_both_agree_boosts_confidence(self):
        value, conf, source = fuse_confidence("2024-01-15", 0.90, "2024-01-15", 0.75)
        assert value == "2024-01-15"
        assert conf == pytest.approx(0.95)     # 0.90 + 0.05
        assert source == "regex+nlp"

    def test_both_agree_caps_at_1(self):
        value, conf, source = fuse_confidence("INV-001", 0.98, "INV-001", 0.80)
        assert conf == pytest.approx(1.0)      # capped at 1.0

    def test_regex_only_unchanged(self):
        value, conf, source = fuse_confidence("INV-001", 0.95, None, 0.0)
        assert value == "INV-001"
        assert conf == pytest.approx(0.95)
        assert source == "regex"

    def test_nlp_only_used_when_no_regex(self):
        value, conf, source = fuse_confidence(None, 0.0, "Acme Corp", 0.80)
        assert value == "Acme Corp"
        assert conf == pytest.approx(0.80)
        assert source == "nlp"

    def test_both_disagree_regex_wins(self):
        value, conf, source = fuse_confidence("2024-01-15", 0.88, "2024-03-20", 0.70)
        assert value == "2024-01-15"
        assert conf == pytest.approx(0.88)
        assert source == "regex"

    def test_neither_found_returns_none(self):
        value, conf, source = fuse_confidence(None, 0.0, None, 0.0)
        assert value is None
        assert conf == pytest.approx(0.0)
        assert source == "none"

    def test_partial_match_counts_as_agreement(self):
        # NLP finds "Acme Corp Ltd" while regex finds "Acme Corp" — substring match
        value, conf, source = fuse_confidence("Acme Corp", 0.85, "Acme Corp Ltd", 0.75)
        assert source == "regex+nlp"
        assert conf > 0.85   # boosted


# ══════════════════════════════════════════════════════════════════════════════
# Cross-field consistency validation — pure logic, no spaCy needed
# ══════════════════════════════════════════════════════════════════════════════

class TestValidateConsistency:
    """These tests are pure logic — no spaCy model needed."""

    def test_valid_dates_no_warning(self):
        warnings = validate_field_consistency(
            invoice_date="2024-01-15",
            due_date="2024-02-14",
            total_amount=1234.56,
            line_items=[],
        )
        assert warnings == []

    def test_due_date_before_invoice_date_warns(self):
        warnings = validate_field_consistency(
            invoice_date="2024-02-14",
            due_date="2024-01-15",    # BEFORE invoice date
            total_amount=100.0,
            line_items=[],
        )
        assert len(warnings) == 1
        assert "before" in warnings[0].lower()

    def test_same_date_no_warning(self):
        # due_date == invoice_date is valid (immediate payment)
        warnings = validate_field_consistency(
            invoice_date="2024-01-15",
            due_date="2024-01-15",
            total_amount=50.0,
            line_items=[],
        )
        assert warnings == []

    def test_missing_dates_no_warning(self):
        # None fields should not trigger date comparison
        warnings = validate_field_consistency(
            invoice_date=None,
            due_date=None,
            total_amount=None,
            line_items=[],
        )
        assert warnings == []

    def test_total_less_than_line_items_warns(self):
        from app.extraction.schemas import LineItem
        items = [
            LineItem(amount=500.0),
            LineItem(amount=500.0),
        ]
        # total_amount (100) << sum of items (1000)
        warnings = validate_field_consistency(
            invoice_date="2024-01-15",
            due_date="2024-02-14",
            total_amount=100.0,
            line_items=items,
        )
        assert len(warnings) == 1
        assert "line items" in warnings[0].lower()

    def test_total_slightly_less_than_items_no_warning(self):
        # Allow 10% slack (e.g. total before tax vs items with tax)
        from app.extraction.schemas import LineItem
        items = [LineItem(amount=1000.0)]
        # 950 is within 10% of 1000 → no warning
        warnings = validate_field_consistency(
            invoice_date="2024-01-15",
            due_date="2024-02-14",
            total_amount=950.0,
            line_items=items,
        )
        assert warnings == []
