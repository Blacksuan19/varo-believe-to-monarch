"""Utility functions."""

import os
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .constants import AMOUNT_DECIMAL_RE, DATE_RE


def default_workers() -> int:
    """Return reasonable default worker count based on CPU cores."""
    return min(8, os.cpu_count() or 4)


def clean(x: Any) -> str:
    """Clean tabs, newlines, and normalize whitespace."""
    if x is None:
        return ""
    s = str(x).replace("\t", " ").replace("\n", " ")
    return " ".join(s.split()).strip()


def is_date(s: str) -> bool:
    """Check if string matches date pattern MM/DD/YYYY."""
    return bool(DATE_RE.fullmatch(s.strip()))


def parse_amount(s: str) -> Optional[float]:
    """Parse string into float amount, handling parentheses and currency symbols."""
    if not s:
        return None
    # Avoid false positives like apartment numbers / street numbers.
    # We only treat tokens as monetary amounts if they look like currency
    # (contain a decimal point and/or are wrapped like ($12.34)).
    s = s.replace(",", "").replace(" ", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    # Strip currency symbol after handling parentheses.
    s = s.replace("$", "")
    if "." not in s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def is_probable_amount_token(token: str) -> bool:
    """Check if token looks like a monetary amount."""
    t = clean(token)
    if not t:
        return False
    if "$" in t or t.startswith("("):
        return parse_amount(t) is not None
    # Some PDFs drop the $ but preserve two decimals.
    if AMOUNT_DECIMAL_RE.fullmatch(t) is not None:
        return True
    return False


def find_pdfs(folder: Path, pattern: str) -> list[Path]:
    """Recursively find PDF files matching pattern."""
    return sorted(p for p in folder.rglob(pattern) if p.is_file())


def latest_pdf_by_date(result: pd.DataFrame, pdfs: list[Path]) -> Path:
    """Return the PDF whose latest transaction date is most recent.

    Uses the Date column in *result* (already in MM/DD/YYYY format) grouped by
    SourceFile so the answer is driven by statement content, not filesystem
    metadata.  Falls back to the last entry in *pdfs* (alphabetically sorted)
    if the lookup fails for any reason.
    """
    fallback = pdfs[-1]
    try:
        pdf_by_name = {p.name: p for p in pdfs}
        latest_name = (
            result.assign(
                _d=pd.to_datetime(result["Date"], format="%m/%d/%Y", errors="coerce")
            )
            .groupby("SourceFile")["_d"]
            .max()
            .idxmax()
        )
        return pdf_by_name.get(latest_name, fallback)
    except Exception:
        return fallback
