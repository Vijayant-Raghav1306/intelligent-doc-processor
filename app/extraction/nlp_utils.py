"""
NLP utility functions — pure helpers built on spaCy Doc objects.

Design contract
───────────────
  • Every function accepts a spaCy Doc (already processed) — never raw text.
    The extractor calls nlp(text) once, then passes doc to all helpers here.
    This avoids redundant inference passes (each nlp() call runs the full
    pipeline, which is ~10-50ms).

  • Every function returns None or [] on failure — never raises.
    Missing entities are normal; callers decide how to handle them.

  • Functions are pure: no side effects, no logging, no I/O.
    Easy to unit-test with synthetic Doc objects.

  • Confidence values returned here are HEURISTIC scores (0.0-1.0).
    spaCy does not expose raw NER probabilities in its default pipeline.
    We infer confidence from:
      - Entity label specificity (MONEY > CARDINAL for amounts)
      - Proximity to a relevant label keyword
      - Entity length / structure (short ORGs are less reliable)
      - Whether the entity spans a known pattern

Typical usage in an extractor
──────────────────────────────
    from app.extraction.nlp_service import get_nlp
    from app.extraction.nlp_utils import (
        extract_org_entities, extract_date_entities, extract_money_entities,
        find_entity_near_keyword,
    )

    nlp = get_nlp()
    doc = nlp(self.clean_text) if nlp else None

    if doc:
        orgs  = extract_org_entities(doc)
        dates = extract_date_entities(doc)
        money = extract_money_entities(doc)
"""
import re
from typing import Optional

# Type alias — a list of (text, confidence) tuples
EntityList = list[tuple[str, float]]


# ── Organisation / Vendor Extraction ─────────────────────────────────────────

def extract_org_entities(doc) -> EntityList:
    """
    Return all ORG entities from the doc, with heuristic confidence scores.

    spaCy's ORG label covers:
      "Acme Corp", "Microsoft", "XYZ Pvt. Ltd.", "the United Nations"

    Confidence heuristics:
      0.75  baseline — spaCy said ORG
      +0.10  if the text contains an org-suffix (Ltd, Inc, LLC, ...)
      +0.05  if the entity appears in the first 10 lines of the document
              (company names typically live in the header)
      -0.10  if the entity is very short (≤ 3 chars) — likely a false positive
      -0.10  if the entity is all-lowercase (companies rarely are)

    Returns:
        List of (entity_text, confidence) sorted by confidence descending.
        Empty list if no ORG entities found.
    """
    _ORG_SUFFIX = re.compile(
        r'\b(?:Ltd\.?|Limited|Inc\.?|LLC|LLP|Corp\.?|Corporation|'
        r'GmbH|S\.A\.?|Pvt\.?\s*Ltd\.?|Private\s+Limited|PLC|AG|BV)\b',
        re.IGNORECASE,
    )

    # Find what line each entity is on (to detect header ORGs)
    lines = doc.text.splitlines()
    first_10_text = "\n".join(lines[:10]).lower()

    results: EntityList = []
    seen: set[str] = set()   # deduplicate by text

    for ent in doc.ents:
        if ent.label_ != "ORG":
            continue

        text = ent.text.strip()
        if not text or text in seen:
            continue
        seen.add(text)

        conf = 0.75   # baseline: spaCy confidently labelled this ORG

        # Boost: known org suffix present
        if _ORG_SUFFIX.search(text):
            conf += 0.10

        # Boost: appears in the first 10 lines (header area)
        if text.lower() in first_10_text:
            conf += 0.05

        # Penalty: very short — "US", "EU", "Ltd" alone are false positives
        if len(text) <= 3:
            conf -= 0.10

        # Penalty: all lowercase (unlikely to be a company name)
        if text == text.lower() and len(text) > 3:
            conf -= 0.10

        results.append((text, min(round(conf, 2), 1.0)))

    # Highest confidence first
    return sorted(results, key=lambda x: x[1], reverse=True)


# ── Date Extraction ───────────────────────────────────────────────────────────

def extract_date_entities(doc) -> EntityList:
    """
    Return all DATE entities from the doc with heuristic confidence.

    spaCy DATE label covers:
      "15 January 2024", "Jan 15, 2024", "2024-01-15", "yesterday", "last week"

    Relative dates ("yesterday", "last month") are NOT useful for invoices.
    We filter those out and assign lower confidence to short date strings
    that might be ambiguous ("January" alone, "2024" alone).

    Returns:
        List of (entity_text, confidence) sorted by confidence descending.
    """
    _RELATIVE = re.compile(
        r'\b(?:yesterday|today|tomorrow|last\s+\w+|next\s+\w+|'
        r'this\s+\w+|ago|since|recently|now)\b',
        re.IGNORECASE,
    )

    results: EntityList = []
    seen: set[str] = set()

    for ent in doc.ents:
        if ent.label_ != "DATE":
            continue

        text = ent.text.strip()
        if not text or text in seen:
            continue
        seen.add(text)

        # Skip relative dates — not useful for invoice fields
        if _RELATIVE.search(text):
            continue

        conf = 0.70   # baseline

        # Boost: contains a year (4-digit number 19xx-20xx)
        if re.search(r'\b(19|20)\d{2}\b', text):
            conf += 0.10

        # Boost: contains a month name
        if re.search(
            r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|'
            r'Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|'
            r'Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\b',
            text, re.IGNORECASE,
        ):
            conf += 0.05

        # Boost: numeric date format (digits + separator + digits)
        if re.search(r'\d{1,4}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}', text):
            conf += 0.10

        # Penalty: very short — just "January" or "2024" — too ambiguous
        if len(text.split()) == 1:
            conf -= 0.15

        results.append((text, min(round(conf, 2), 1.0)))

    return sorted(results, key=lambda x: x[1], reverse=True)


# ── Money / Amount Extraction ─────────────────────────────────────────────────

def extract_money_entities(doc) -> EntityList:
    """
    Return all MONEY entities from the doc with heuristic confidence.

    spaCy MONEY label covers:
      "$1,234.56", "USD 3,750", "one thousand dollars", "€1.234,56"

    We also pick up CARDINAL entities (plain numbers) that immediately
    follow a currency symbol/code — spaCy sometimes labels "$1,234" as
    two tokens: "$" (SYM) + "1,234" (CARDINAL).

    Returns:
        List of (entity_text, confidence) sorted by confidence descending.
    """
    _CURRENCY_SYM = re.compile(r'[\$£€₹¥]|USD|EUR|GBP|INR|JPY|AUD|CAD|CHF')

    results: EntityList = []
    seen: set[str] = set()

    for ent in doc.ents:
        if ent.label_ not in ("MONEY", "CARDINAL"):
            continue

        text = ent.text.strip()
        if not text or text in seen:
            continue

        # For CARDINAL, only accept it if it looks like a monetary amount
        if ent.label_ == "CARDINAL":
            if not re.search(r'[\d,\.]+', text):
                continue
            # Only include CARDINAL if it follows a currency symbol token
            prev_token = doc[ent.start - 1] if ent.start > 0 else None
            if prev_token is None or not _CURRENCY_SYM.search(prev_token.text):
                continue

        seen.add(text)
        conf = 0.72   # baseline for MONEY

        if ent.label_ == "CARDINAL":
            conf = 0.55   # lower baseline — context-dependent

        # Boost: has a currency symbol or ISO code in the text
        if _CURRENCY_SYM.search(text):
            conf += 0.10

        # Boost: has a numeric value with decimal
        if re.search(r'\d+[.,]\d{1,2}', text):
            conf += 0.08

        # Penalty: spelled out ("one thousand") — hard to normalize reliably
        if re.search(r'[a-zA-Z]{4,}', text) and not _CURRENCY_SYM.search(text):
            conf -= 0.15

        results.append((text, min(round(conf, 2), 1.0)))

    return sorted(results, key=lambda x: x[1], reverse=True)


# ── Contextual Entity Search ───────────────────────────────────────────────────

def find_entity_near_keyword(
    doc,
    keyword: str,
    entity_label: str,
    window_tokens: int = 8,
) -> Optional[tuple[str, float]]:
    """
    Find the first entity of the given label within `window_tokens` tokens
    of any occurrence of `keyword` in the doc.

    This is how we bridge "Invoice Date:" (a label) with the DATE entity
    that follows it — without a rigid regex. It handles OCR-distorted labels
    like "Invoice  Date :" or "lnvoice Date" where the regex might miss.

    Args:
        doc:           spaCy Doc object.
        keyword:       The label to search for (e.g. "invoice", "total").
                       Case-insensitive token match.
        entity_label:  spaCy entity type to look for (e.g. "DATE", "MONEY").
        window_tokens: How many tokens after/before the keyword to search.
                       Default 8 covers "Invoice Date: 15 January 2024".

    Returns:
        (entity_text, confidence) of the closest matching entity, or None.

    Example:
        find_entity_near_keyword(doc, "invoice", "DATE", window_tokens=6)
        → ("15 January 2024", 0.80)
    """
    keyword_lower = keyword.lower()

    # Build a lookup: entity_start_token_idx → Span
    ent_by_start: dict[int, object] = {ent.start: ent for ent in doc.ents}

    for token in doc:
        if token.lower_ != keyword_lower:
            continue

        # Search forward within window
        search_end = min(token.i + window_tokens, len(doc))
        for j in range(token.i, search_end):
            if j in ent_by_start:
                ent = ent_by_start[j]
                if ent.label_ == entity_label:  # type: ignore[attr-defined]
                    # Closer → higher confidence (within-window proximity bonus)
                    proximity_bonus = round(
                        (window_tokens - (j - token.i)) / window_tokens * 0.10, 2
                    )
                    return (ent.text.strip(), round(0.75 + proximity_bonus, 2))

    return None


# ── Confidence Fusion ─────────────────────────────────────────────────────────

def fuse_confidence(
    regex_value,
    regex_conf: float,
    nlp_value,
    nlp_conf: float,
) -> tuple[any, float, str]:
    """
    Merge a regex result and an NLP result into a single best answer.

    Fusion rules (conservative — we trust the deterministic regex more):

      Both found, same value  → regex_value, min(regex_conf + 0.05, 1.0)
                                 "Both agree — boost by 5%"

      Both found, different   → regex_value, regex_conf
                                 "Trust the labeled pattern; add a warning"

      Only regex found        → regex_value, regex_conf
                                 "NLP didn't help — keep regex result"

      Only NLP found          → nlp_value,   nlp_conf
                                 "No labeled match — take NLP's suggestion"

      Neither found           → None, 0.0

    Args:
        regex_value:  Value returned by regex extractor (or None).
        regex_conf:   Confidence of regex result (0.0 if nothing found).
        nlp_value:    Value returned by NLP extractor (or None).
        nlp_conf:     Confidence of NLP result (0.0 if nothing found).

    Returns:
        (chosen_value, final_confidence, source_tag)
        source_tag is one of: "regex+nlp", "regex", "nlp", "none"
    """
    regex_found = regex_value is not None and regex_conf > 0.0
    nlp_found   = nlp_value   is not None and nlp_conf   > 0.0

    if regex_found and nlp_found:
        # Normalize to string for comparison (handles float ≈ equality)
        r_str = str(regex_value).lower().strip()
        n_str = str(nlp_value).lower().strip()
        if r_str == n_str or n_str in r_str or r_str in n_str:
            return regex_value, min(regex_conf + 0.05, 1.0), "regex+nlp"
        else:
            # Values differ — trust regex, caller should log a warning
            return regex_value, regex_conf, "regex"

    if regex_found:
        return regex_value, regex_conf, "regex"

    if nlp_found:
        return nlp_value, nlp_conf, "nlp"

    return None, 0.0, "none"


# ── Validation Helpers ────────────────────────────────────────────────────────

def validate_field_consistency(
    invoice_date: Optional[str],
    due_date: Optional[str],
    total_amount: Optional[float],
    line_items: list,
) -> list[str]:
    """
    Cross-field sanity checks — returns a list of warning strings.

    These checks catch extraction errors by verifying that extracted fields
    are mutually consistent:
      - due_date should be on or after invoice_date
      - total_amount should be ≥ the sum of line item amounts (gross check)

    Returns:
        List of warning strings (empty if all checks pass).
    """
    warnings: list[str] = []

    # Check: due_date must not be before invoice_date
    if invoice_date and due_date:
        if due_date < invoice_date:   # ISO 8601 strings sort lexicographically
            warnings.append(
                f"Consistency check: due_date ({due_date}) is before "
                f"invoice_date ({invoice_date}) — extraction may be wrong."
            )

    # Check: total_amount should be ≥ sum of line item amounts
    if total_amount is not None and line_items:
        item_total = sum(
            item.amount for item in line_items
            if item.amount is not None
        )
        if item_total > 0 and total_amount < item_total * 0.90:
            # Allow 10% slack for rounding / tax not in line items
            warnings.append(
                f"Consistency check: total_amount ({total_amount:.2f}) is "
                f"less than sum of line items ({item_total:.2f}) — "
                "possible extraction error."
            )

    return warnings
