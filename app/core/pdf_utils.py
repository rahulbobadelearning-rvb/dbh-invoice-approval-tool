# REMARK: PDF handling is intentionally minimal — we store the original
# file untouched and attempt best-effort text extraction for convenience.
# SHA-256 hash is the canonical duplicate-detection mechanism because
# it is collision-resistant and content-based (independent of filename).

import hashlib
import re
import shutil
from pathlib import Path
from typing import Optional

import pdfplumber

from core.db import PDF_STORAGE


def compute_sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def save_pdf(file_bytes: bytes, filename: str, vendor_code: str) -> Path:
    """
    Persist the uploaded PDF under data/invoices/<vendor_code>/<filename>.
    Returns the absolute path stored in the DB.
    """
    vendor_dir = PDF_STORAGE / vendor_code
    vendor_dir.mkdir(parents=True, exist_ok=True)
    dest = vendor_dir / filename
    dest.write_bytes(file_bytes)
    return dest


def extract_text(file_bytes: bytes) -> str:
    """
    Return all text extracted from the PDF, concatenated page by page.
    Returns empty string on any extraction failure (corrupt, scanned, etc.).
    """
    try:
        import io
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Heuristic field extraction from raw PDF text
# These are "best effort" — the user always confirms values in the form.
# ---------------------------------------------------------------------------

_AMOUNT_RE = re.compile(
    r"""
    (?:total|amount\s+due|invoice\s+amount|grand\s+total|net\s+amount)
    [\s:]*
    [\$€£]?\s*
    ([\d,]+(?:\.\d{1,2})?)
    """,
    re.IGNORECASE | re.VERBOSE,
)
_INVOICE_NO_RE = re.compile(
    r"(?:invoice\s+(?:no|number|#|num)[.:]*\s*)([A-Z0-9\-/]+)",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"(?:invoice\s+date|date\s+of\s+invoice|issued)[.:]*\s*"
    r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\d{4}[/\-]\d{2}[/\-]\d{2})"
    r"|(\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b)",
    re.IGNORECASE,
)


def try_extract_amount(text: str) -> Optional[float]:
    match = _AMOUNT_RE.search(text)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def try_extract_invoice_number(text: str) -> Optional[str]:
    match = _INVOICE_NO_RE.search(text)
    return match.group(1).strip() if match else None


def try_extract_date(text: str) -> Optional[str]:
    """Return date as ISO YYYY-MM-DD if parseable, else None."""
    match = _DATE_RE.search(text)
    if not match:
        return None
    raw = (match.group(1) or match.group(2) or "").strip()
    return _normalise_date(raw)


def _normalise_date(raw: str) -> Optional[str]:
    """Attempt to parse common date formats into ISO YYYY-MM-DD."""
    from datetime import datetime
    formats = [
        "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y",
        "%d.%m.%Y", "%d %B %Y", "%d %b %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None
