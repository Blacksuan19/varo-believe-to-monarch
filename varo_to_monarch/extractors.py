"""PDF extraction logic using Camelot and pdfplumber."""
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import camelot
import pandas as pd
import pdfplumber

from .constants import DATE_RE, SECTION_ORDER
from .utils import (
    clean,
    is_date,
    is_probable_amount_token,
    parse_amount,
)


@dataclass(frozen=True)
class Heading:
    name: str
    top: float


def row_to_raw_fields(cells: list[str]) -> tuple[str, str, str]:
    """Return (date, description, amount) from a Camelot row.

    Standard format: Date | Description | Amount (3 columns)
    """
    cleaned = [clean(c) for c in cells]

    if len(cleaned) == 0:
        return "", "", ""

    # Standard 3-column format: Date | Description | Amount
    if len(cleaned) >= 3:
        date = cleaned[0]
        amount = cleaned[-1]
        desc = " ".join(cleaned[1:-1])
        return date, desc, amount

    # 2 columns: try to figure out what they are
    if len(cleaned) == 2:
        if is_date(cleaned[0]):
            # Date | Amount (no description)
            return cleaned[0], "", cleaned[1]
        if is_probable_amount_token(cleaned[1]):
            # Description | Amount
            return "", cleaned[0], cleaned[1]

    # Single column or fallback
    return cleaned[0] if cleaned else "", "", ""


def extract_text_based_transactions(pdf_path: str) -> pd.DataFrame:
    """
    Extract transactions from sections that Camelot misses using pdfplumber text parsing.
    Specifically targets 'Payments and Credits' and 'Secured Account Transactions'.
    """
    raw_data: list[dict[str, Any]] = []
    source = Path(pdf_path).name

    # Only extract sections that Camelot can't handle well
    TARGET_SECTIONS = ["Payments and Credits", "Secured Account Transactions"]

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""

            for section in TARGET_SECTIONS:
                if section not in text:
                    continue

                # Find section start
                section_start = text.find(section)
                if section_start == -1:
                    continue

                # Extract text after section heading until next section or end
                remaining = text[section_start + len(section) :]

                # Find where this section ends (next section heading or end of text)
                section_end = len(remaining)
                for other_section in SECTION_ORDER:
                    if other_section != section:
                        pos = remaining.find(other_section)
                        if pos != -1 and pos < section_end:
                            section_end = pos

                section_text = remaining[:section_end]
                lines = section_text.split("\n")

                # Parse transactions: look for lines starting with date pattern
                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    if not line:
                        i += 1
                        continue

                    # Check if line starts with a date
                    parts = line.split()
                    if not parts or not DATE_RE.match(parts[0]):
                        i += 1
                        continue

                    date = parts[0]

                    # Amount is last token with $
                    amount = ""
                    for token in reversed(parts):
                        if "$" in token:
                            amount = token
                            break

                    if not amount:
                        i += 1
                        continue

                    # Description is everything between date and amount on current line
                    desc_parts = []
                    for token in parts[1:]:
                        if token == amount:
                            break
                        desc_parts.append(token)

                    # Check if previous line is a description (doesn't start with date, no table header)
                    if i > 0:
                        prev_line = lines[i - 1].strip()
                        if prev_line and not prev_line.lower().startswith(
                            ("date", "description", "amount")
                        ):
                            prev_parts = prev_line.split()
                            if (
                                prev_parts
                                and not DATE_RE.match(prev_parts[0])
                                and "$" not in prev_line
                            ):
                                # Previous line is part of description
                                desc_parts.insert(0, prev_line)

                    description = " ".join(desc_parts).strip()

                    raw_data.append(
                        {
                            "Date": date,
                            "Merchant": clean(description),
                            "AmountRaw": amount,
                            "Section": section,
                            "SourceFile": source,
                        }
                    )

                    i += 1

    if not raw_data:
        return pd.DataFrame()

    df = pd.DataFrame(raw_data)
    df["AmountParsed"] = df["AmountRaw"].apply(parse_amount)
    df = df.dropna(subset=["AmountParsed"])

    return df[["Date", "Merchant", "AmountParsed", "Section", "SourceFile"]].copy()


def extract_transactions_from_pdf(pdf_path: str) -> pd.DataFrame:
    """
    Extract transactions, build raw rows with date/desc/amount, merge in pandas.

    Extract transactions from PDF tables using Camelot.

    We rely on the statement structure:
    - section heading table(s)
    - followed by transaction table(s) in that section
    """
    raw_data: list[dict[str, Any]] = []
    source = Path(pdf_path).name

    # Use stream with row_tol=15 (best results from testing)
    tables = camelot.read_pdf(
        pdf_path,
        pages="all",
        flavor="stream",
        row_tol=15,
    )

    current_section = "Purchases"

    for idx, table in enumerate(tables, start=1):
        tdf: pd.DataFrame = table.df
        if tdf is None or tdf.empty:
            continue

        # Process each row
        for row_num, row in enumerate(tdf.itertuples(index=False), start=1):
            cells = [clean(c) for c in list(row)]
            if not any(cells):
                continue

            # Check if this row is a section heading
            joined = " ".join(cells).strip()
            for sec in SECTION_ORDER:
                if joined == sec:
                    current_section = sec
                    break

            # Skip header rows and summary rows
            jl = joined.lower()
            if "date" in jl and "description" in jl and "amount" in jl:
                continue
            if jl.startswith("total ") or jl.startswith("summary "):
                continue
            if joined in SECTION_ORDER:
                continue

            date, desc, amount = row_to_raw_fields(cells)

            # Must have at least a date to be a valid transaction row
            if not is_date(date):
                continue

            # Must have an amount
            if not amount or parse_amount(amount) is None:
                continue

            raw_data.append(
                {
                    "SourceFile": source,
                    "Page": int(getattr(table, "page", 0) or 0),
                    "Table": idx,
                    "Row": row_num,
                    "Section": current_section,
                    "Date": date,
                    "Description": desc,
                    "Amount": amount,
                }
            )

    if not raw_data:
        return pd.DataFrame()

    df = pd.DataFrame(raw_data)

    # Mark transaction starts (rows with valid dates)
    df["IsTransactionStart"] = df["Date"].apply(is_date)

    # Within each (file, page, table, section), assign transaction IDs
    # Increment ID whenever we hit a transaction start
    group_keys = ["SourceFile", "Page", "Table", "Section"]
    df = df.sort_values(group_keys + ["Row"]).copy()
    df["TxnIdIncrement"] = df["IsTransactionStart"].astype(int)
    df["TxnId"] = df.groupby(group_keys)["TxnIdIncrement"].cumsum()

    # Drop rows before first transaction (TxnId == 0)
    df = df[df["TxnId"] > 0].copy()

    # Merge rows by transaction ID
    merged = (
        df.groupby(group_keys + ["TxnId"], sort=False)
        .agg(
            Date=("Date", lambda s: next((x for x in s if is_date(x)), "")),
            Merchant=("Description", lambda s: " ".join(x for x in s if x).strip()),
            AmountRaw=(
                "Amount",
                lambda s: next((x for x in s if parse_amount(x) is not None), ""),
            ),
        )
        .reset_index()
    )

    merged["AmountParsed"] = merged["AmountRaw"].apply(parse_amount)
    merged = merged.dropna(subset=["AmountParsed"])

    camelot_df = merged[
        ["Date", "Merchant", "AmountParsed", "Section", "SourceFile"]
    ].copy()

    # Extract text-based transactions for sections Camelot misses
    text_df = extract_text_based_transactions(pdf_path)

    # Combine: Camelot for Purchases/Fees, text parsing for Payments/Secured
    if not text_df.empty:
        combined = pd.concat([camelot_df, text_df], ignore_index=True)
        return combined

    return camelot_df
