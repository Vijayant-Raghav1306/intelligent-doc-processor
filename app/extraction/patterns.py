"""
Centralized regex pattern library for document extraction.

Structure of each entry:
    (compiled_regex, confidence_score)

  compiled_regex  — must capture the target value in group 1
  confidence      — float 0.0-1.0; higher = stronger contextual evidence

Patterns are ordered from highest to lowest confidence within each list.
Extractors iterate the list and return on the first successful match.

Regex flag used throughout: re.IGNORECASE | re.MULTILINE
  IGNORECASE  — invoices use mixed casing ("Invoice No", "INVOICE NO", "invoice no")
  MULTILINE   — ^ and $ anchor to line boundaries, not document boundaries
"""
import re

_F = re.IGNORECASE | re.MULTILINE


# ── Invoice Number ─────────────────────────────────────────────────────────────
#
# Invoice numbers are alphanumeric identifiers, 3-25 chars, often with
# hyphens or slashes.  We look for labeled context first.
#
# Group 1 captures the identifier itself.

INVOICE_NUMBER: list[tuple[re.Pattern, float]] = [

    # 0.95 — "Invoice Number: INV-2024-001" or "Invoice No: B-00123"
    (re.compile(
        r'invoice\s*(?:no\.?|number|num\.?|#|id)\s*[:\-]?\s*'
        r'([A-Z0-9][A-Z0-9\-_/]{2,24})',
        _F,
    ), 0.95),

    # 0.90 — "Bill Number: 00123" or "Bill No: ABC/001"
    (re.compile(
        r'bill\s*(?:no\.?|number|#)\s*[:\-]?\s*'
        r'([A-Z0-9][A-Z0-9\-_/]{2,24})',
        _F,
    ), 0.90),

    # 0.85 — "Receipt No: REC-001"
    (re.compile(
        r'receipt\s*(?:no\.?|number|#)\s*[:\-]?\s*'
        r'([A-Z0-9][A-Z0-9\-_/]{2,24})',
        _F,
    ), 0.85),

    # 0.75 — "Ref: INV-001" or "Reference: 2024/001"
    (re.compile(
        r'ref(?:erence)?\s*(?:no\.?|#)?\s*[:\-]\s*'
        r'([A-Z0-9][A-Z0-9\-_/]{2,24})',
        _F,
    ), 0.75),

    # 0.80 — Bare structured prefix: INV-, BILL-, REC-, PO-, ORD-
    # These are recognizable even without a label.
    (re.compile(
        r'\b((?:INV|BILL|REC|REF|ORD|PO|SI|SB)[-/][A-Z0-9][-A-Z0-9]{1,20})\b',
        _F,
    ), 0.80),
]


# ── Invoice Date ───────────────────────────────────────────────────────────────
#
# We capture raw date strings here; normalization to ISO 8601 happens in
# normalizers.normalize_date().  This keeps regex simple and normalization
# logic in one tested place.
#
# Two date surface forms:
#   Numeric:   DD/MM/YYYY  DD-MM-YYYY  YYYY-MM-DD  DD.MM.YYYY
#   Textual:   15 January 2024   January 15, 2024   15 Jan 2024

_DATE_NUM  = r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})'
_DATE_TEXT = r'(\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4})'
_DATE_TEXT2 = r'((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4})'
_DATE_ISO  = r'(\d{4}[/\-]\d{2}[/\-]\d{2})'

INVOICE_DATE: list[tuple[re.Pattern, float]] = [

    # 0.95 — "Invoice Date: 15/01/2024"
    (re.compile(r'invoice\s+date\s*[:\-]?\s*' + _DATE_NUM,  _F), 0.95),
    (re.compile(r'invoice\s+date\s*[:\-]?\s*' + _DATE_TEXT, _F), 0.95),
    (re.compile(r'invoice\s+date\s*[:\-]?\s*' + _DATE_TEXT2,_F), 0.95),
    (re.compile(r'invoice\s+date\s*[:\-]?\s*' + _DATE_ISO,  _F), 0.95),

    # 0.88 — "Issue Date:", "Issued:", "Dated:"
    (re.compile(r'(?:issue[d]?|dated?)\s*(?:on\s*)?[:\-]?\s*' + _DATE_NUM,  _F), 0.88),
    (re.compile(r'(?:issue[d]?|dated?)\s*(?:on\s*)?[:\-]?\s*' + _DATE_TEXT, _F), 0.88),
    (re.compile(r'(?:issue[d]?|dated?)\s*(?:on\s*)?[:\-]?\s*' + _DATE_TEXT2,_F), 0.88),

    # 0.75 — Bare "Date: 15/01/2024" — common but ambiguous
    (re.compile(r'(?<!\w)date\s*[:\-]\s*' + _DATE_NUM,  _F), 0.75),
    (re.compile(r'(?<!\w)date\s*[:\-]\s*' + _DATE_TEXT, _F), 0.75),
    (re.compile(r'(?<!\w)date\s*[:\-]\s*' + _DATE_TEXT2,_F), 0.75),
    (re.compile(r'(?<!\w)date\s*[:\-]\s*' + _DATE_ISO,  _F), 0.75),
]


# ── Due Date ───────────────────────────────────────────────────────────────────

DUE_DATE: list[tuple[re.Pattern, float]] = [

    # 0.95 — "Due Date: 15/02/2024" or "Payment Due: ..."
    (re.compile(r'due\s+date\s*[:\-]?\s*' + _DATE_NUM,   _F), 0.95),
    (re.compile(r'due\s+date\s*[:\-]?\s*' + _DATE_TEXT,  _F), 0.95),
    (re.compile(r'due\s+date\s*[:\-]?\s*' + _DATE_TEXT2, _F), 0.95),
    (re.compile(r'payment\s+due\s*[:\-]?\s*' + _DATE_NUM,_F), 0.95),

    # 0.90 — "Due By:", "Pay By:", "Payable By:"
    (re.compile(r'(?:due|pay(?:able)?)\s+by\s*[:\-]?\s*' + _DATE_NUM,  _F), 0.90),
    (re.compile(r'(?:due|pay(?:able)?)\s+by\s*[:\-]?\s*' + _DATE_TEXT, _F), 0.90),

    # 0.85 — "Payment Date:", "Expiry:", "Expires:"
    (re.compile(r'payment\s+date\s*[:\-]?\s*' + _DATE_NUM, _F), 0.85),
]

# Net terms pattern — "Net 30", "Net 60", "Net 90"
# Not a date itself; invoice_extractor uses this to compute due_date from invoice_date.
NET_TERMS = re.compile(r'\bnet\s*(\d+)\b', _F)


# ── Total Amount ───────────────────────────────────────────────────────────────
#
# The total amount is the final payable figure — NOT the subtotal.
# We specifically avoid matching "subtotal", "sub-total", "tax" alone.
#
# The number capture group handles:
#   1,234.56    US format
#   1.234,56    European format (normalizer handles conversion)
#   1 234.56    space as thousands separator
#   1234.56     no separator
#   1,23,456.78 Indian format
#
# Currency symbols/codes before the number are captured in group 1 (optional),
# the numeric value is captured in group 2.

_CURR_PREFIX = r'([\$£€₹¥]|(?:USD|EUR|GBP|INR|JPY|AUD|CAD|CHF|CNY)\b)?\s*'

# _AMOUNT_VAL captures the raw amount token; normalize_amount() resolves the format.
#
# Alt 1: \d+  -- leading digits (no {1,3} cap, so '1180' is captured whole)
#   (?:[,\.]\d{2,3})*  -- 0+ thousands groups: ',234' (US/EU), '.234' (EU), ',23' (Indian)
#   (?:[,.]\d{1,2})?   -- optional trailing decimal (1-2 digits)
#   (?:\s*[KkMm])?     -- optional K/M suffix
# Alt 2: space-as-thousands  e.g. '1 234.56'
_AMOUNT_VAL = (
    r'('
    r'\d+(?:[,\.]\d{2,3})*(?:[,.]\d{1,2})?(?:\s*[KkMm])?'
    r'|\d+(?:[ ]\d{3})+(?:[,.]\d{1,2})?(?:\s*[KkMm])?'
    r')'
)

TOTAL_AMOUNT: list[tuple[re.Pattern, float]] = [

    # 0.97 — "Grand Total: $1,234.56"
    (re.compile(r'grand\s+total\s*[:\-]?\s*' + _CURR_PREFIX + _AMOUNT_VAL, _F), 0.97),

    # 0.95 — "Total Amount Due: 1234.56" or "Amount Due: ..."
    (re.compile(r'total\s+amount\s+due\s*[:\-]?\s*' + _CURR_PREFIX + _AMOUNT_VAL, _F), 0.95),
    (re.compile(r'amount\s+due\s*[:\-]?\s*'          + _CURR_PREFIX + _AMOUNT_VAL, _F), 0.95),

    # 0.92 — "Balance Due:", "Net Due:", "Total Due:"
    (re.compile(r'(?:balance|net|total)\s+due\s*[:\-]?\s*' + _CURR_PREFIX + _AMOUNT_VAL, _F), 0.92),

    # 0.90 — "Amount Payable:", "Total Payable:"
    (re.compile(r'(?:amount|total)\s+payable\s*[:\-]?\s*' + _CURR_PREFIX + _AMOUNT_VAL, _F), 0.90),

    # 0.80 — Bare "Total: 1234.56" — common but could appear near subtotals
    # Negative lookbehind for "sub" prevents matching "subtotal"
    (re.compile(r'(?<!sub)(?<!sub-)total\s*[:\-]?\s*' + _CURR_PREFIX + _AMOUNT_VAL, _F), 0.80),
]


# ── Currency Detection ─────────────────────────────────────────────────────────

# Maps symbols and common text forms → ISO 4217 codes
CURRENCY_MAP: dict[str, str] = {
    "$":   "USD",   "us$": "USD",  "usd": "USD",
    "£":   "GBP",   "gbp": "GBP",
    "€":   "EUR",   "eur": "EUR",
    "₹":   "INR",   "inr": "INR",  "rs": "INR",  "rs.": "INR",  "inr.": "INR",
    "¥":   "JPY",   "jpy": "JPY",
    "a$":  "AUD",   "aud": "AUD",
    "c$":  "CAD",   "cad": "CAD",
    "chf": "CHF",
    "cny": "CNY",   "¥cn": "CNY",
    "sgd": "SGD",   "s$": "SGD",
    "hkd": "HKD",   "hk$": "HKD",
    "nzd": "NZD",   "nz$": "NZD",
    "aed": "AED",   "sar": "SAR",
    "myr": "MYR",   "rm":  "MYR",
}

# Regex that matches any known currency symbol/code in text
CURRENCY_IN_TEXT = re.compile(
    r'\b(USD|EUR|GBP|INR|JPY|AUD|CAD|CHF|CNY|SGD|HKD|NZD|AED|SAR|MYR)\b'
    r'|(?<!\w)([\$£€₹¥]|Rs\.?|RM)\b',
    _F,
)


# ── Vendor / Company Name ──────────────────────────────────────────────────────
#
# Vendor name is the hardest field — it has no consistent format.
# Strategy (in order of confidence):
#   1. Explicit label: "From:", "Vendor:", "Billed by:", "Company:"
#   2. Organisation suffix: "Acme Ltd", "XYZ Inc", "Foo Corp"
#   3. Heuristic: first meaningful line in top portion of document

ORG_SUFFIXES = re.compile(
    r'\b(?:Ltd\.?|Limited|Inc\.?|Incorporated|LLC|LLP|Corp\.?|'
    r'Corporation|GmbH|S\.A\.?|Pvt\.?\s*Ltd\.?|Private\s+Limited|'
    r'PLC|AG|BV|NV|SRL|SAS|SARL|OÜ|OY|AB|AS|ApS)\b',
    _F,
)

VENDOR_LABELED: list[tuple[re.Pattern, float]] = [
    # 0.92 — "From: Acme Corp" or "Vendor: XYZ Ltd"
    (re.compile(r'^(?:from|vendor|billed?\s+(?:by|from)|seller|supplier)\s*[:\-]\s*(.+)$', _F), 0.92),
    # 0.85 — "Company: Acme Corp" or "Company Name: ..."
    (re.compile(r'^company\s*(?:name)?\s*[:\-]\s*(.+)$', _F), 0.85),
    # 0.80 — "Service Provider: ..."
    (re.compile(r'^service\s+provider\s*[:\-]\s*(.+)$', _F), 0.80),
]
