"""
Unit tests for app/extraction/normalizers.py

Every function is pure (no I/O, no side effects), so tests are
fast and straightforward: input string → expected output.

Coverage targets
────────────────
  clean_text          — whitespace edge cases
  normalize_date      — 16 format variants + ambiguous / invalid inputs
  compute_due_date    — correct offset, bad input
  normalize_amount    — US, European, Indian, K/M, symbols, invalid
  normalize_currency  — symbols, codes, case-insensitive, unknown
  detect_currency_in_text — scan a block of text
"""
import pytest

from app.extraction.normalizers import (
    clean_text,
    compute_due_date,
    detect_currency_in_text,
    normalize_amount,
    normalize_currency,
    normalize_date,
)


# ══════════════════════════════════════════════════════════════════════════════
# clean_text
# ══════════════════════════════════════════════════════════════════════════════

class TestCleanText:
    def test_crlf_normalized(self):
        assert "\n" in clean_text("line1\r\nline2")
        assert "\r" not in clean_text("line1\r\nline2")

    def test_cr_only_normalized(self):
        assert "\r" not in clean_text("line1\rline2")

    def test_tabs_collapsed(self):
        result = clean_text("col1\t\tcol2")
        assert "\t" not in result
        assert "col1 col2" == result

    def test_multiple_spaces_collapsed(self):
        assert clean_text("a    b") == "a b"

    def test_three_or_more_blank_lines_collapsed(self):
        result = clean_text("a\n\n\n\n\nb")
        assert result == "a\n\nb"

    def test_two_blank_lines_preserved(self):
        result = clean_text("a\n\nb")
        assert result == "a\n\nb"

    def test_leading_trailing_whitespace_stripped(self):
        assert clean_text("  hello  ") == "hello"

    def test_empty_string(self):
        assert clean_text("") == ""

    def test_already_clean(self):
        assert clean_text("hello world") == "hello world"


# ══════════════════════════════════════════════════════════════════════════════
# normalize_date
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizeDate:

    # ── Formats that must succeed ─────────────────────────────────────────────

    @pytest.mark.parametrize("raw,expected", [
        ("2024-01-15",      "2024-01-15"),   # ISO
        ("2024/01/15",      "2024-01-15"),   # ISO slash
        ("15/01/2024",      "2024-01-15"),   # DD/MM/YYYY (default prefer_dmy)
        ("15-01-2024",      "2024-01-15"),   # DD-MM-YYYY
        ("15.01.2024",      "2024-01-15"),   # DD.MM.YYYY
        ("15 January 2024", "2024-01-15"),   # full month name DD first
        ("January 15, 2024","2024-01-15"),   # full month name US
        ("15 Jan 2024",     "2024-01-15"),   # abbreviated
        ("Jan 15, 2024",    "2024-01-15"),   # abbreviated US
        ("15-Jan-2024",     "2024-01-15"),   # dash abbreviated
        ("15-Jan-24",       "2024-01-15"),   # 2-digit year
        ("15/01/24",        "2024-01-15"),   # numeric 2-digit
    ])
    def test_valid_formats(self, raw, expected):
        assert normalize_date(raw) == expected

    # ── Trailing punctuation stripped before parsing ──────────────────────────

    def test_trailing_period_stripped(self):
        assert normalize_date("15/01/2024.") == "2024-01-15"

    def test_trailing_comma_stripped(self):
        assert normalize_date("15/01/2024,") == "2024-01-15"

    # ── Unambiguous day > 12 forces DMY ──────────────────────────────────────

    def test_day_gt_12_forces_dmy(self):
        # 20/01/2024 — day=20 > 12 → must be 20 Jan
        assert normalize_date("20/01/2024") == "2024-01-20"

    # ── prefer_dmy=False switches order ──────────────────────────────────────

    def test_prefer_mdy(self):
        # 01/02/2024 with prefer_dmy=False → MM/DD/YYYY is tried first
        # %m/%d/%Y → month=01, day=02 → January 2, 2024
        result = normalize_date("01/02/2024", prefer_dmy=False)
        assert result == "2024-01-02"

    # ── Year sanity guard ─────────────────────────────────────────────────────

    def test_year_out_of_range_returns_none(self):
        assert normalize_date("15/01/1899") is None
        assert normalize_date("15/01/2200") is None

    # ── Invalid input returns None ────────────────────────────────────────────

    def test_garbage_input(self):
        assert normalize_date("not a date") is None

    def test_empty_string(self):
        assert normalize_date("") is None

    def test_partial_date(self):
        assert normalize_date("15/01") is None


# ══════════════════════════════════════════════════════════════════════════════
# compute_due_date
# ══════════════════════════════════════════════════════════════════════════════

class TestComputeDueDate:
    def test_net_30(self):
        assert compute_due_date("2024-01-15", 30) == "2024-02-14"

    def test_net_60(self):
        assert compute_due_date("2024-01-15", 60) == "2024-03-15"

    def test_net_0(self):
        assert compute_due_date("2024-01-15", 0) == "2024-01-15"

    def test_end_of_month_overflow(self):
        # Jan 31 + 1 day = Feb 1 (not Jan 32)
        assert compute_due_date("2024-01-31", 1) == "2024-02-01"

    def test_bad_invoice_date_returns_none(self):
        assert compute_due_date("not-a-date", 30) is None


# ══════════════════════════════════════════════════════════════════════════════
# normalize_amount
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizeAmount:

    # ── Standard formats ─────────────────────────────────────────────────────

    @pytest.mark.parametrize("raw,expected", [
        ("1234.56",       1234.56),   # plain decimal
        ("1,234.56",      1234.56),   # US thousands
        ("1.234,56",      1234.56),   # European
        ("1 234.56",      1234.56),   # space thousands
        ("1,23,456.78",   123456.78), # Indian
        ("1234",          1234.0),    # integer
        ("0.99",          0.99),      # fraction only
    ])
    def test_standard_formats(self, raw, expected):
        assert normalize_amount(raw) == expected

    # ── Currency symbols / codes stripped ────────────────────────────────────

    @pytest.mark.parametrize("raw,expected", [
        ("$1,234.56",   1234.56),
        ("£1,234.56",   1234.56),
        ("€1.234,56",   1234.56),
        ("₹1,234",      1234.0),
        ("USD 1234.56", 1234.56),
        ("INR 1,234",   1234.0),
        ("Rs. 500",     500.0),
    ])
    def test_currency_prefix_stripped(self, raw, expected):
        assert normalize_amount(raw) == expected

    # ── K / M suffixes ────────────────────────────────────────────────────────

    @pytest.mark.parametrize("raw,expected", [
        ("1.2K",    1200.0),
        ("2.5M",  2500000.0),
        ("1K",     1000.0),
        ("10M", 10000000.0),
        ("1.5k",   1500.0),   # lowercase
    ])
    def test_k_m_suffixes(self, raw, expected):
        assert normalize_amount(raw) == expected

    # ── European thousands (multiple dots) ────────────────────────────────────

    def test_european_thousands_dots(self):
        # "1.234.567" — multiple dots → all are thousands separators
        assert normalize_amount("1.234.567") == 1234567.0

    # ── Invalid / empty input ─────────────────────────────────────────────────

    def test_empty_string(self):
        assert normalize_amount("") is None

    def test_non_numeric(self):
        assert normalize_amount("N/A") is None

    def test_negative_rejected(self):
        # normalize_amount rejects negative values (invoices don't have them)
        assert normalize_amount("-500") is None

    def test_above_1_trillion_rejected(self):
        assert normalize_amount("2000000000000") is None   # 2 trillion


# ══════════════════════════════════════════════════════════════════════════════
# normalize_currency
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizeCurrency:

    @pytest.mark.parametrize("raw,expected", [
        ("$",    "USD"),
        ("£",    "GBP"),
        ("€",    "EUR"),
        ("₹",    "INR"),
        ("¥",    "JPY"),
        ("USD",  "USD"),
        ("usd",  "USD"),   # case-insensitive
        ("EUR",  "EUR"),
        ("inr",  "INR"),
        ("Rs",   "INR"),
        ("rs.",  "INR"),
        ("RM",   "MYR"),
        ("SGD",  "SGD"),
    ])
    def test_known_symbols_and_codes(self, raw, expected):
        assert normalize_currency(raw) == expected

    def test_unknown_3_letter_code_passthrough(self):
        # An unrecognised but valid ISO-pattern code is returned as-is
        result = normalize_currency("XYZ")
        assert result == "XYZ"

    def test_empty_string_returns_none(self):
        assert normalize_currency("") is None

    def test_garbage_returns_none(self):
        assert normalize_currency("not-a-currency") is None

    def test_whitespace_stripped(self):
        assert normalize_currency("  USD  ") == "USD"


# ══════════════════════════════════════════════════════════════════════════════
# detect_currency_in_text
# ══════════════════════════════════════════════════════════════════════════════

class TestDetectCurrencyInText:

    def test_detects_usd_code(self):
        assert detect_currency_in_text("Total: USD 1,234.56") == "USD"

    def test_detects_dollar_symbol(self):
        assert detect_currency_in_text("Grand Total $500.00") == "USD"

    def test_detects_inr_symbol(self):
        assert detect_currency_in_text("Amount: ₹12,000") == "INR"

    def test_detects_gbp_code(self):
        assert detect_currency_in_text("Invoice total GBP 999") == "GBP"

    def test_detects_rs_prefix(self):
        assert detect_currency_in_text("Rs. 5,000") == "INR"

    def test_no_currency_returns_none(self):
        assert detect_currency_in_text("Hello world, no money here.") is None

    def test_empty_string(self):
        assert detect_currency_in_text("") is None

    def test_first_match_wins(self):
        # Both USD and EUR appear — the first one (USD) should be returned
        result = detect_currency_in_text("USD 100 and EUR 200")
        assert result == "USD"
