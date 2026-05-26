"""
InvoiceExtractor — hybrid regex + NLP extraction.

Extraction strategy (per field)
────────────────────────────────
  invoice_number  regex-only   NLP has no concept of "invoice number"
  invoice_date    hybrid       regex labeled match → NLP DATE near keyword → fallback
  due_date        hybrid       regex labeled match → NLP DATE near "due" → Net terms
  total_amount    hybrid       regex labeled match → NLP MONEY near "total" → fallback
  currency        hybrid       total-line scan → NLP MONEY prefix → full-text scan
  vendor_name     NLP-first    ORG entity near header → regex label → first-line heuristic

Confidence fusion
─────────────────
  Both regex AND NLP agree  → confidence boosted by +0.05 (max 1.0)
  Only regex found          → confidence unchanged
  Only NLP found            → NLP heuristic confidence
  Both found, disagree      → regex wins, warning logged

NLP is optional
───────────────
  If spaCy is not installed or the model failed to load, every field
  falls back to the same regex logic as before Phase 4.
  All 200 tests from Phases 1-3 still pass unchanged.
"""
import re
from typing import Optional

from app.core.logging_config import get_logger
from app.extraction.base_extractor import BaseExtractor
from app.extraction.nlp_service import get_nlp
from app.extraction.nlp_utils import (
    extract_date_entities,
    extract_money_entities,
    extract_org_entities,
    find_entity_near_keyword,
    fuse_confidence,
    validate_field_consistency,
)
from app.extraction.normalizers import (
    compute_due_date,
    detect_currency_in_text,
    normalize_amount,
    normalize_currency,
    normalize_date,
)
from app.extraction.patterns import (
    DUE_DATE,
    INVOICE_DATE,
    INVOICE_NUMBER,
    NET_TERMS,
    ORG_SUFFIXES,
    TOTAL_AMOUNT,
    VENDOR_LABELED,
)
from app.extraction.schemas import (
    FieldConfidence,
    InvoiceExtractionResult,
    InvoiceFields,
    LineItem,
)

logger = get_logger(__name__)

_FALLBACK_CONFIDENCE = 0.40


class InvoiceExtractor(BaseExtractor):
    """
    Extract structured invoice fields from raw document text.

    Usage:
        result = InvoiceExtractor(raw_text).extract()

    The NLP model is loaded once at startup (nlp_service.load_nlp()).
    If unavailable, the extractor silently uses regex-only mode.
    """

    def __init__(self, text: str) -> None:
        super().__init__(text)

        # Run the spaCy pipeline once per document, reuse the Doc everywhere.
        # nlp(text) is ~10-50ms; calling it per-field would multiply that cost.
        nlp = get_nlp()
        self._doc = nlp(self.clean_text) if nlp is not None else None

        if self._doc is not None:
            logger.debug(
                "NLP doc created",
                extra={"entities": len(self._doc.ents), "tokens": len(self._doc)},
            )

    # ── Public entry point ────────────────────────────────────────────────────

    def extract(self) -> InvoiceExtractionResult:
        """
        Run all field extractors and assemble the final result.

        Never raises. Internal errors become extraction_warnings entries.
        """
        warnings: list[str] = []

        # ── Per-field extraction ──────────────────────────────────────────────
        vendor_name,    conf_vendor   = self._safe_extract(self._extract_vendor_name,    warnings)
        invoice_number, conf_inv_num  = self._safe_extract(self._extract_invoice_number, warnings)
        invoice_date,   conf_inv_date = self._safe_extract(self._extract_invoice_date,   warnings)
        due_date,       conf_due_date = self._safe_extract(self._extract_due_date,       warnings, invoice_date)
        total_amount,   conf_total    = self._safe_extract(self._extract_total_amount,   warnings)
        currency,       conf_currency = self._safe_extract(self._extract_currency,       warnings)
        line_items                    = self._safe_extract_items(warnings)

        # ── Cross-field consistency checks ────────────────────────────────────
        consistency_warnings = validate_field_consistency(
            invoice_date, due_date, total_amount, line_items
        )
        warnings.extend(consistency_warnings)

        # ── Assemble result ───────────────────────────────────────────────────
        result = InvoiceExtractionResult(
            fields=InvoiceFields(
                vendor_name=vendor_name,
                invoice_number=invoice_number,
                invoice_date=invoice_date,
                due_date=due_date,
                total_amount=total_amount,
                currency=currency,
                line_items=line_items,
            ),
            confidence=FieldConfidence(
                vendor_name=conf_vendor,
                invoice_number=conf_inv_num,
                invoice_date=conf_inv_date,
                due_date=conf_due_date,
                total_amount=conf_total,
                currency=conf_currency,
            ),
            extraction_warnings=warnings,
            raw_text_length=len(self.raw_text),
        )

        logger.info(
            "Invoice extraction complete",
            extra={
                "overall_confidence": result.overall_confidence,
                "nlp_active": self._doc is not None,
                "fields_found": sum(
                    1 for v in result.fields.model_dump().values()
                    if v not in (None, [], "")
                ),
                "warnings": len(warnings),
            },
        )

        return result

    # ── Error isolation wrapper ───────────────────────────────────────────────

    def _safe_extract(self, method, warnings: list[str], *args):
        try:
            return method(*args)
        except Exception as exc:  # noqa: BLE001
            field = method.__name__.replace("_extract_", "")
            msg = f"Extractor error in {field}: {exc!r}"
            warnings.append(msg)
            logger.warning(msg)
            return None, 0.0

    def _safe_extract_items(self, warnings: list[str]) -> list[LineItem]:
        try:
            return self._extract_line_items()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Extractor error in line_items: {exc!r}")
            return []

    # ── 1. Invoice Number (regex-only) ────────────────────────────────────────

    def _extract_invoice_number(self) -> tuple[Optional[str], float]:
        """
        Regex-only — NLP has no concept of "invoice number".

        spaCy's generic NER does not recognise "INV-2024-001" as a special
        entity type. It might tag it as ORG or CARDINAL depending on context,
        which would be noise. Regex patterns are far more precise here.

        This is a good example of where deterministic rules OUTPERFORM NLP.
        """
        for pattern, confidence in INVOICE_NUMBER:
            m = pattern.search(self.clean_text)
            if m:
                value = m.group(1).strip()
                logger.debug("invoice_number matched", extra={"conf": confidence, "value": value})
                return value, confidence

        return None, 0.0

    # ── 2. Invoice Date (hybrid) ──────────────────────────────────────────────

    def _extract_invoice_date(self) -> tuple[Optional[str], float]:
        """
        Strategy:
          1. Regex labeled match (highest confidence — explicit label)
          2. NLP: DATE entity near the word "invoice" (contextual)
          3. NLP: DATE entity near the word "date"
          4. Fallback: first date anywhere in the document

        Fusion: if both regex and NLP agree → confidence boosted.
        """
        # ── Step 1: regex labeled patterns ───────────────────────────────────
        regex_value, regex_conf = None, 0.0
        for pattern, confidence in INVOICE_DATE:
            m = pattern.search(self.clean_text)
            if m:
                raw = m.group(1).strip()
                iso = normalize_date(raw)
                if iso:
                    regex_value, regex_conf = iso, confidence
                    break

        # ── Step 2: NLP DATE near "invoice" ──────────────────────────────────
        nlp_value, nlp_conf = None, 0.0
        if self._doc is not None:
            # Try "invoice" first, then "date" as label keyword
            for keyword in ("invoice", "date", "issued", "dated"):
                hit = find_entity_near_keyword(self._doc, keyword, "DATE", window_tokens=8)
                if hit:
                    raw, base_conf = hit
                    iso = normalize_date(raw)
                    if iso:
                        nlp_value, nlp_conf = iso, base_conf
                        break

            # Also scan all DATE entities as a broader fallback
            if not nlp_value:
                for raw, base_conf in extract_date_entities(self._doc):
                    iso = normalize_date(raw)
                    if iso:
                        nlp_value, nlp_conf = iso, base_conf * 0.85  # slightly discounted
                        break

        # ── Fuse results ──────────────────────────────────────────────────────
        value, conf, source = fuse_confidence(regex_value, regex_conf, nlp_value, nlp_conf)

        if value:
            logger.debug("invoice_date resolved", extra={"value": value, "conf": conf, "source": source})
            return value, conf

        # ── Step 3: document-wide fallback ───────────────────────────────────
        return self._fallback_first_date("invoice_date")

    # ── 3. Due Date (hybrid) ──────────────────────────────────────────────────

    def _extract_due_date(
        self, invoice_date: Optional[str] = None
    ) -> tuple[Optional[str], float]:
        """
        Strategy:
          1. Regex labeled patterns (DUE_DATE list)
          2. NLP: DATE entity near "due" / "pay" / "payment"
          3. Net terms: "Net 30" + invoice_date → compute due date
        """
        # ── Regex labeled patterns ────────────────────────────────────────────
        regex_value, regex_conf = None, 0.0
        for pattern, confidence in DUE_DATE:
            m = pattern.search(self.clean_text)
            if m:
                raw = m.group(1).strip()
                iso = normalize_date(raw)
                if iso:
                    regex_value, regex_conf = iso, confidence
                    break

        # ── NLP: DATE near payment-related keywords ───────────────────────────
        nlp_value, nlp_conf = None, 0.0
        if self._doc is not None:
            for keyword in ("due", "pay", "payment", "payable"):
                hit = find_entity_near_keyword(self._doc, keyword, "DATE", window_tokens=8)
                if hit:
                    raw, base_conf = hit
                    iso = normalize_date(raw)
                    if iso and iso != regex_value:   # don't pick up invoice_date again
                        nlp_value, nlp_conf = iso, base_conf
                        break

        # ── Fuse ──────────────────────────────────────────────────────────────
        value, conf, source = fuse_confidence(regex_value, regex_conf, nlp_value, nlp_conf)
        if value:
            logger.debug("due_date resolved", extra={"value": value, "conf": conf, "source": source})
            return value, conf

        # ── Net terms fallback ────────────────────────────────────────────────
        m = NET_TERMS.search(self.clean_text)
        if m and invoice_date:
            net_days = int(m.group(1))
            if 1 <= net_days <= 365:
                computed = compute_due_date(invoice_date, net_days)
                if computed:
                    logger.debug("due_date from net terms", extra={"net_days": net_days})
                    return computed, 0.70

        return None, 0.0

    # ── 4. Total Amount (hybrid) ──────────────────────────────────────────────

    def _extract_total_amount(self) -> tuple[Optional[float], float]:
        """
        Strategy:
          1. Regex labeled patterns (highest confidence — Grand Total, etc.)
          2. NLP: MONEY entity near "total" / "grand" / "amount due"
          3. Fuse: if both find the same value → boost confidence

        Why regex-first here:
          The TOTAL_AMOUNT pattern list is highly specific (Grand Total, Amount Due,
          etc.) and reliably identifies the correct line. NLP might find any MONEY
          entity — taxes, subtotals, line item prices. So we don't trust NLP alone
          for total amount; it only boosts regex confidence.
        """
        # ── Regex patterns ────────────────────────────────────────────────────
        regex_value, regex_conf = None, 0.0
        for pattern, confidence in TOTAL_AMOUNT:
            m = pattern.search(self.clean_text)
            if m:
                raw_amount = (
                    m.group(2).strip()
                    if m.lastindex and m.lastindex >= 2
                    else m.group(1).strip()
                )
                value = normalize_amount(raw_amount)
                if value is not None:
                    regex_value, regex_conf = value, confidence
                    break

        # ── NLP: MONEY near total-related keywords ────────────────────────────
        nlp_value, nlp_conf = None, 0.0
        if self._doc is not None:
            for keyword in ("total", "grand", "due", "payable"):
                hit = find_entity_near_keyword(self._doc, keyword, "MONEY", window_tokens=6)
                if hit:
                    raw, base_conf = hit
                    parsed = normalize_amount(raw)
                    if parsed is not None:
                        nlp_value, nlp_conf = parsed, base_conf
                        break

            # Broader fallback: highest-confidence MONEY entity
            if nlp_value is None:
                for raw, base_conf in extract_money_entities(self._doc):
                    parsed = normalize_amount(raw)
                    if parsed is not None:
                        nlp_value, nlp_conf = parsed, base_conf * 0.80
                        break

        value, conf, source = fuse_confidence(regex_value, regex_conf, nlp_value, nlp_conf)
        if value is not None:
            logger.debug("total_amount resolved", extra={"value": value, "conf": conf, "source": source})
            return value, conf

        return None, 0.0

    # ── 5. Currency (hybrid) ──────────────────────────────────────────────────

    def _extract_currency(self) -> tuple[Optional[str], float]:
        """
        Strategy:
          1. Scan total amount line for currency prefix (high confidence — in context)
          2. NLP: extract currency from MONEY entities' prefix tokens
          3. Scan full text for any currency symbol/code
        """
        # ── Strategy 1: currency symbol on the total-amount line ─────────────
        total_line = self._find_total_line()
        if total_line:
            currency = detect_currency_in_text(total_line)
            if currency:
                logger.debug("currency from total line", extra={"currency": currency})
                return currency, 0.90

        # ── Strategy 2: currency from NLP MONEY entities ──────────────────────
        if self._doc is not None:
            for raw, _ in extract_money_entities(self._doc):
                currency = detect_currency_in_text(raw)
                if currency:
                    logger.debug("currency from NLP MONEY entity", extra={"currency": currency})
                    return currency, 0.78

        # ── Strategy 3: full-text scan ────────────────────────────────────────
        currency = detect_currency_in_text(self.clean_text)
        if currency:
            logger.debug("currency from full-text scan", extra={"currency": currency})
            return currency, 0.65

        return None, 0.0

    # ── 6. Vendor Name (NLP-first) ────────────────────────────────────────────

    def _extract_vendor_name(self) -> tuple[Optional[str], float]:
        """
        NLP-first — this is where spaCy helps most.

        Why NLP is preferred here:
          Vendor names have no consistent format. "Acme Corp", "XYZ Pvt. Ltd.",
          "Skyline Solutions" — none of these follow a pattern. The only signal
          is that they appear near the top of the document AND look like an org.
          spaCy's ORG entity covers all of these without custom patterns.

        Strategy:
          1. NLP: ORG entities from the first 10 lines (header area)
          2. Regex labeled: "From:", "Vendor:", "Company:", "Billed by:"
          3. ORG suffix heuristic: any line in first 30 lines with Ltd/Inc/LLC
          4. First meaningful non-numeric, non-label line (last resort)

        Fusion note:
          For vendor_name, we run NLP first (reversed priority vs other fields).
          If NLP finds an ORG in the header AND regex finds a labeled "Vendor:",
          we still prefer NLP if its confidence is higher (header ORGs are reliable).
        """
        nlp_value, nlp_conf = None, 0.0

        # ── NLP: ORG entities ─────────────────────────────────────────────────
        if self._doc is not None:
            orgs = extract_org_entities(self._doc)
            if orgs:
                # Take the highest-confidence ORG entity
                nlp_value, nlp_conf = orgs[0]
                logger.debug("vendor_name NLP candidate", extra={"name": nlp_value, "conf": nlp_conf})

        # ── Regex: labeled vendor patterns ────────────────────────────────────
        regex_value, regex_conf = None, 0.0
        for pattern, confidence in VENDOR_LABELED:
            m = pattern.search(self.clean_text)
            if m:
                regex_value = m.group(1).strip()[:120]
                regex_conf  = confidence
                break

        # ── Fuse: NLP-first for vendor ────────────────────────────────────────
        # We slightly prefer NLP here (unlike other fields) because labeled
        # "Vendor: ..." is rare in real invoices — the name just appears at top.
        if nlp_value and regex_value:
            n_str = nlp_value.lower()
            r_str = regex_value.lower()
            if n_str in r_str or r_str in n_str:
                # Same entity — take whichever has higher confidence
                if nlp_conf >= regex_conf:
                    return nlp_value, min(nlp_conf + 0.05, 1.0)
                else:
                    return regex_value, min(regex_conf + 0.05, 1.0)
            # Different — defer to labeled regex (more specific signal)
            return regex_value, regex_conf

        if nlp_value:
            return nlp_value, nlp_conf

        if regex_value:
            return regex_value, regex_conf

        # ── ORG suffix scan (heuristic) ───────────────────────────────────────
        lines = self.clean_text.splitlines()
        for line in lines[:30]:
            stripped = line.strip()
            if not stripped:
                continue
            if ORG_SUFFIXES.search(stripped):
                return stripped[:120], 0.65

        # ── First meaningful line (last resort) ───────────────────────────────
        for line in lines[:10]:
            stripped = line.strip()
            if len(stripped) < 4:
                continue
            if re.fullmatch(r'[\d\s\-/.:,]+', stripped):
                continue
            if re.match(r'^(invoice|bill|receipt|date|to:|from:|ref)', stripped, re.IGNORECASE):
                continue
            return stripped[:120], 0.30

        return None, 0.0

    # ── 7. Line Items ─────────────────────────────────────────────────────────

    def _extract_line_items(self) -> list[LineItem]:
        """
        Column-alignment table parser (unchanged from Phase 3).

        Why no NLP here:
          Line item tables are structured data, not natural language.
          Regex / column-alignment heuristics are more reliable than NER
          for tabular content. spaCy would tokenize each row and might
          tag amounts as MONEY or CARDINAL — but it has no concept of
          "this MONEY value is in the 'amount' column of a table".

          Future: LayoutLM or table-detection models would be the right
          tool to improve line item extraction.
        """
        items: list[LineItem] = []
        raw_lines = re.sub(r'\r\n|\r', '\n', self.raw_text)
        lines = raw_lines.splitlines()

        header_re = re.compile(r'description|item|particulars', re.IGNORECASE)
        price_re  = re.compile(r'price|amount|total|rate|charge', re.IGNORECASE)
        qty_re    = re.compile(r'qty|quantity|units?|nos?\.?|count', re.IGNORECASE)

        header_idx = None
        for i, line in enumerate(lines):
            if header_re.search(line) and (qty_re.search(line) or price_re.search(line)):
                header_idx = i
                break

        if header_idx is None:
            return []

        stop_re = re.compile(
            r'^\s*(?:sub\s*[-]?\s*total|grand\s+total|total\s+amount|'
            r'discount|tax\s*(?:@|:|\d)|vat|gst|cgst|sgst|igst|'
            r'balance\s+due|amount\s+due|net\s+total)',
            re.IGNORECASE,
        )

        num_re = re.compile(r'^[\$£€₹]?\s*[\d,\.]+\s*[KkMm]?$')

        for line in lines[header_idx + 1:]:
            stripped = line.strip()
            if not stripped:
                continue
            if stop_re.match(stripped):
                break

            cols = re.split(r'\s{2,}|\t+', stripped)
            cols = [c.strip() for c in cols if c.strip()]

            if len(cols) < 2:
                continue

            item = self._parse_line_item_cols(cols, num_re)
            if item is not None:
                items.append(item)

        logger.debug("line_items extracted", extra={"count": len(items)})
        return items

    def _parse_line_item_cols(
        self, cols: list[str], num_re: re.Pattern
    ) -> Optional[LineItem]:
        is_num = [bool(num_re.match(c)) for c in cols]

        if not any(is_num):
            return None

        amount_idx = max(i for i, n in enumerate(is_num) if n)
        amount_val = normalize_amount(cols[amount_idx])

        unit_price_idx = None
        unit_price_val = None
        numeric_indices = [i for i, n in enumerate(is_num) if n]
        if len(numeric_indices) >= 2:
            unit_price_idx = numeric_indices[-2]
            unit_price_val = normalize_amount(cols[unit_price_idx])

        qty_val = None
        for i in numeric_indices:
            if i in (amount_idx, unit_price_idx):
                continue
            parsed = normalize_amount(cols[i])
            if parsed is not None and parsed == int(parsed) and parsed <= 9999:
                qty_val = parsed
                break

        text_cols = [
            cols[i] for i, n in enumerate(is_num)
            if not n and i not in (amount_idx, unit_price_idx)
        ]
        description = " ".join(text_cols).strip() or None

        if description is None and qty_val is None and amount_val is None:
            return None

        return LineItem(
            description=description,
            quantity=qty_val,
            unit_price=unit_price_val,
            amount=amount_val,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _fallback_first_date(self, field_name: str) -> tuple[Optional[str], float]:
        date_anywhere = re.compile(
            r'\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b'
            r'|\b(\d{4}[/\-]\d{2}[/\-]\d{2})\b'
            r'|\b(\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|'
            r'Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|'
            r'Nov(?:ember)?|Dec(?:ember)?)\s+\d{4})\b',
            re.IGNORECASE,
        )
        for m in date_anywhere.finditer(self.clean_text):
            raw = (m.group(1) or m.group(2) or m.group(3) or "").strip()
            iso = normalize_date(raw)
            if iso:
                logger.debug(f"{field_name} fallback date", extra={"raw": raw, "iso": iso})
                return iso, _FALLBACK_CONFIDENCE
        return None, 0.0

    def _find_total_line(self) -> Optional[str]:
        total_kw = re.compile(
            r'total|amount\s+due|grand\s+total|balance\s+due', re.IGNORECASE
        )
        for line in self.clean_text.splitlines():
            if total_kw.search(line):
                return line
        return None
