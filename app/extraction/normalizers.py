"""
Normalization utilities for extracted raw strings.

All functions are pure — no side effects, no logging, no I/O.
Return None on failure rather than raising; callers decide how to handle it.

Design contract:
  normalize_date(raw)     → "YYYY-MM-DD"  | None
  normalize_amount(raw)   → float          | None
  normalize_currency(raw) → "USD"          | None  (ISO 4217)
  clean_text(raw)         → str            (always succeeds)
"""
import re
from datetime import datetime, timedelta


# ── Text Cleaning ─────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """
    Normalize whitespace in raw OCR/document text.

    Steps:
      1. Normalize line endings (CRLF, CR → LF)
      2. Collapse horizontal whitespace (tabs, multiple spaces → single space)
      3. Collapse vertical whitespace (3+ newlines → 2 newlines)
      4. Strip leading/trailing whitespace
    """
    text = re.sub(r'\r\n|\r', '\n', text)       # normalize line endings
    text = re.sub(r'[ \t]+', ' ', text)          # collapse horizontal space
    text = re.sub(r'\n{3,}', '\n\n', text)       # collapse excessive blank lines
    return text.strip()


# ── Date Normalization ────────────────────────────────────────────────────────

# Ordered list of format strings to try.
# We try more-specific formats first to avoid ambiguous short matches.
_DATE_FORMATS = [
    # ISO and reverse
    "%Y-%m-%d",         # 2024-01-15
    "%Y/%m/%d",         # 2024/01/15

    # Full month name
    "%d %B %Y",         # 15 January 2024
    "%B %d, %Y",        # January 15, 2024
    "%B %d %Y",         # January 15 2024

    # Abbreviated month name
    "%d %b %Y",         # 15 Jan 2024
    "%b %d, %Y",        # Jan 15, 2024
    "%b %d %Y",         # Jan 15 2024
    "%d-%b-%Y",         # 15-Jan-2024
    "%d-%b-%y",         # 15-Jan-24

    # Numeric (4-digit year)
    "%d/%m/%Y",         # 15/01/2024  (international default — DD first)
    "%m/%d/%Y",         # 01/15/2024  (US format — tried second)
    "%d-%m-%Y",         # 15-01-2024
    "%d.%m.%Y",         # 15.01.2024

    # Numeric (2-digit year)
    "%d/%m/%y",         # 15/01/24
    "%m/%d/%y",         # 01/15/24
]


def normalize_date(raw: str, *, prefer_dmy: bool = True) -> str | None:
    """
    Parse a raw date string and return ISO 8601 "YYYY-MM-DD".

    Args:
        raw:        The raw string extracted by regex (e.g. "15/01/2024").
        prefer_dmy: When True (default), DD/MM/YYYY is tried before MM/DD/YYYY.
                    Set False for US-context documents.

    Returns:
        ISO 8601 string on success, None if no format matched.

    Ambiguity note:
        "01/02/2024" could be 1 Feb or 2 Jan.
        If day_part > 12, it cannot be a month → unambiguously DD/MM/YYYY.
        Otherwise we rely on prefer_dmy and note the ambiguity.
    """
    raw = raw.strip()

    # Remove trailing punctuation that sometimes bleeds in from OCR
    raw = raw.rstrip('.,;:')

    # Quick unambiguity check for numeric dates
    _num_parts = re.split(r'[/\-\.]', raw)
    if len(_num_parts) == 3 and _num_parts[0].isdigit():
        first = int(_num_parts[0])
        if first > 12:
            # Day > 12 → cannot be a month → must be DD/MM/YYYY
            prefer_dmy = True

    formats = _DATE_FORMATS if prefer_dmy else (
        [f for f in _DATE_FORMATS if f not in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y")]
        + ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"]
    )

    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
            # Sanity: reject obviously wrong years
            if not (1990 <= dt.year <= 2100):
                continue
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def compute_due_date(invoice_date_iso: str, net_days: int) -> str | None:
    """
    Compute due date from invoice date + net payment terms.
    e.g. invoice_date="2024-01-15", net_days=30 → "2024-02-14"
    """
    try:
        dt = datetime.strptime(invoice_date_iso, "%Y-%m-%d")
        due = dt + timedelta(days=net_days)
        return due.strftime("%Y-%m-%d")
    except ValueError:
        return None


# ── Amount Normalization ──────────────────────────────────────────────────────

def normalize_amount(raw: str) -> float | None:
    """
    Convert a raw amount string to a Python float.

    Handles:
      "1,234.56"      → 1234.56   (US format)
      "1.234,56"      → 1234.56   (European format)
      "1 234.56"      → 1234.56   (space as thousands separator)
      "1,23,456.78"   → 123456.78 (Indian format)
      "1234.56"       → 1234.56   (plain)
      "$1,234.56"     → 1234.56   (strip currency symbol)
      "1.2K"          → 1200.0    (abbreviated thousands)
      "1.5M"          → 1500000.0 (abbreviated millions)
      "INR 1,234"     → 1234.0    (strip currency code)

    Returns None if the string cannot be parsed.
    """
    if not raw:
        return None

    # Strip currency symbols, codes, and surrounding whitespace
    raw = _strip_currency_prefix(raw).strip()

    if not raw:
        return None

    # Handle K / M suffixes  ("1.2K", "2.5M")
    km_match = re.fullmatch(r'([\d,\. ]+)\s*([KkMm])', raw)
    if km_match:
        base = _parse_numeric(km_match.group(1))
        if base is None:
            return None
        multiplier = 1_000 if km_match.group(2).upper() == 'K' else 1_000_000
        return round(base * multiplier, 2)

    return _parse_numeric(raw)


def _strip_currency_prefix(text: str) -> str:
    """Remove leading/trailing currency symbols and ISO codes."""
    # Remove ISO codes (3-letter, word boundary)
    text = re.sub(
        r'^\s*(?:USD|EUR|GBP|INR|JPY|AUD|CAD|CHF|CNY|SGD|HKD|NZD|AED|SAR|MYR)\b\s*',
        '', text, flags=re.IGNORECASE,
    )
    # Remove trailing ISO code
    text = re.sub(
        r'\s*\b(?:USD|EUR|GBP|INR|JPY|AUD|CAD|CHF|CNY|SGD|HKD|NZD|AED|SAR|MYR)\s*$',
        '', text, flags=re.IGNORECASE,
    )
    # Remove currency symbols and text forms
    text = re.sub(r'^[\$£€₹¥]|^Rs\.?\s*|^RM\s*', '', text.strip(), flags=re.IGNORECASE)
    return text.strip()


def _parse_numeric(text: str) -> float | None:
    """
    Parse a numeric string handling US, European, Indian, and space-separated formats.

    Detection algorithm (handles all common formats):
      Both comma and dot present:
        - Last separator is comma  → European: "1.234,56"  → remove dots, swap comma→dot
        - Last separator is dot    → US:       "1,234.56"  → remove commas
      Only comma:
        - Comma with 1-2 digits after → likely decimal:  "1,5"  → "1.5"
        - Otherwise                   → thousands separator: "1,234" → "1234"
      Only dot:
        - Exactly one dot → decimal point: "1234.56"
        - Multiple dots   → thousands: "1.234.567" → "1234567"
      Spaces only (thousands): "1 234 56" → interpret carefully
    """
    text = text.strip().replace('\xa0', '')  # remove non-breaking spaces too

    # Spaces as thousands separators (e.g. "1 234 567", "1 234.56", "1 234,56")
    # The optional group at the end allows a decimal/comma part after the digits.
    if re.fullmatch(r'\d[\d ]*\d(?:[.,]\d+)?', text) and ' ' in text:
        text = text.replace(' ', '')

    has_comma = ',' in text
    has_dot   = '.' in text

    if has_comma and has_dot:
        last_comma = text.rfind(',')
        last_dot   = text.rfind('.')
        if last_comma > last_dot:
            # European: 1.234,56 — dots are thousands, comma is decimal
            text = text.replace('.', '').replace(',', '.')
        else:
            # US / Indian: 1,234.56  or  1,23,456.78
            text = text.replace(',', '')

    elif has_comma and not has_dot:
        # Could be decimal ("1,50") or thousands ("1,234" or "1,23,456")
        parts = text.split(',')
        last_part = parts[-1]
        if len(parts) == 2 and len(last_part) <= 2:
            # Decimal comma: "1,50" → "1.50"
            text = text.replace(',', '.')
        else:
            # Thousands comma — strip all
            text = text.replace(',', '')

    elif has_dot and not has_comma:
        dot_count = text.count('.')
        if dot_count > 1:
            # Multiple dots = thousands: "1.234.567" → "1234567"
            text = text.replace('.', '')

    try:
        value = float(text)
        # Reject clearly nonsensical values
        if value < 0 or value > 1e12:
            return None
        return round(value, 2)
    except ValueError:
        return None


# ── Currency Normalization ────────────────────────────────────────────────────

from app.extraction.patterns import CURRENCY_MAP   # noqa: E402 (after functions for clarity)


def normalize_currency(raw: str) -> str | None:
    """
    Map a raw currency string to an ISO 4217 three-letter code.

    Handles:
      "$"    → "USD"
      "£"    → "GBP"
      "€"    → "EUR"
      "₹"    → "INR"
      "Rs"   → "INR"
      "USD"  → "USD"
      "inr"  → "INR"  (case-insensitive)

    Returns None if the string is not recognized.
    """
    if not raw:
        return None
    key = raw.strip().lower()
    if key in CURRENCY_MAP:
        return CURRENCY_MAP[key]
    # Try uppercase (handles "USD", "EUR" etc.)
    upper = raw.strip().upper()
    if upper in CURRENCY_MAP:
        return CURRENCY_MAP[upper]
    # Check if it's already a valid ISO 4217 we haven't mapped
    if re.fullmatch(r'[A-Z]{3}', upper):
        return upper
    return None


def detect_currency_in_text(text: str) -> str | None:
    """
    Scan a block of text and return the first ISO 4217 currency code found.
    Used when currency is not explicitly labeled — just present in amounts.
    """
    from app.extraction.patterns import CURRENCY_IN_TEXT
    match = CURRENCY_IN_TEXT.search(text)
    if not match:
        return None
    raw = (match.group(1) or match.group(2) or "").strip()
    return normalize_currency(raw)
