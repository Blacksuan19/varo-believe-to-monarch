"""PDF extraction logic using PyMuPDF and pdfplumber."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import pandas as pd
import pdfplumber

from .constants import DATE_RE, SECTION_ORDER
from .utils import clean, is_date, is_probable_amount_token, parse_amount


@dataclass(frozen=True)
class Heading:
    name: str
    top: float


def is_secured_account_transaction(description: str) -> bool:
    """Check if a transaction description indicates a Secured Account transaction.

    Secured Account transactions are only:
    - Transfers from Secured Account to Believe Card ("Trf from Vault to Charge C Bal")
    - Deposits into Secured Account ("Move Your Pay - Chk to Believe")
    - Transfers from Secured Account to Checking ("Transfer from Vault to DDA")
    """
    desc_lower = description.lower()
    patterns = [
        "trf from vault to charge c bal",
        "transfer from varo believe secured",
        "move your pay - chk to believe",
        "transfer from vault to dda",
    ]
    return any(pattern in desc_lower for pattern in patterns)


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
    Extract transactions using pdfplumber text parsing as fallback/supplement to PyMuPDF.
    This catches transactions that PyMuPDF's table detection might miss.

    Extracts all lines that look like transactions and infers their section from context.
    """
    raw_data: list[dict[str, Any]] = []
    source = Path(pdf_path).name

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            lines = text.split("\n")

            # Track current section based on headers we see
            current_section = "Purchases"  # default, carries across pages

            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue

                # Check if this line is a section header
                for sec in SECTION_ORDER:
                    if line == sec or line.startswith(f"{sec}\n") or line == f"{sec} ":
                        current_section = sec
                        break

                # Check if line starts with a date
                parts = line.split()
                if not parts or not DATE_RE.match(parts[0]):
                    continue

                # Skip the statement period header (e.g., "12/18/2025 - 01/18/2026")
                if len(parts) >= 3 and parts[1] == "-":
                    continue

                date = parts[0]

                # Find amount (last token with $ or looks like money)
                amount = ""
                for token in reversed(parts):
                    if "$" in token or is_probable_amount_token(token):
                        amount = token
                        break

                if not amount:
                    continue

                # Description is everything between date and amount
                desc_parts = []
                for token in parts[1:]:
                    if token == amount:
                        break
                    desc_parts.append(token)

                # Check if previous line is part of description
                if i > 0:
                    prev_line = lines[i - 1].strip()
                    if prev_line and not prev_line.lower() in ("date", "description", "amount"):
                        prev_parts = prev_line.split()
                        if (
                            prev_parts
                            and not DATE_RE.match(prev_parts[0])
                            and "$" not in prev_line
                            and not any(prev_line == sec for sec in SECTION_ORDER)
                        ):
                            # Previous line is part of description
                            desc_parts.insert(0, prev_line)

                description = " ".join(desc_parts).strip()

                raw_data.append(
                    {
                        "Date": date,
                        "Merchant": clean(description),
                        "AmountRaw": amount,
                        "Section": current_section,
                        "SourceFile": source,
                    }
                )

    if not raw_data:
        return pd.DataFrame()

    df = pd.DataFrame(raw_data)
    df["AmountParsed"] = df["AmountRaw"].apply(parse_amount)
    df = df.dropna(subset=["AmountParsed"])

    return df[["Date", "Merchant", "AmountParsed", "Section", "SourceFile"]].copy()


def extract_pymupdf_tables(pdf_path: str) -> pd.DataFrame:
    """
    Extract transactions from PDF tables using PyMuPDF.

    Targets sections where tabular data is present:
    - Purchases
    - Fees
    - Payments and Credits (also captured here if in table format)
    - Secured Account Transactions
    """
    raw_data: list[dict[str, Any]] = []
    source = Path(pdf_path).name

    doc = fitz.open(pdf_path)
    current_section = "Purchases"  # default section, carries across pages

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Extract text blocks to track section headers by position
        text_dict = page.get_text("dict")
        text_blocks = []
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text_content = span.get("text", "").strip()
                        if text_content:
                            text_blocks.append(
                                {"text": text_content, "y": span.get("bbox", [0, 0, 0, 0])[1]}
                            )

        # Find section headers and their Y positions
        section_y_positions = []
        for block in text_blocks:
            for sec in SECTION_ORDER:
                if block["text"] == sec or sec in block["text"]:
                    section_y_positions.append((block["y"], sec))
                    # Update current section when we see a new header
                    current_section = sec
                    break

        section_y_positions.sort()  # Sort by Y position (top to bottom)

        # Extract tables using PyMuPDF's find_tables
        tables = page.find_tables()

        for table_num, table in enumerate(tables, start=1):
            if not table or not table.extract():
                continue

            extracted = table.extract()

            # Determine which section this table belongs to based on Y position
            table_bbox = table.bbox
            table_y = table_bbox[1] if table_bbox else 0

            # Find the closest section header BEFORE this table (on this page)
            table_section = current_section  # Use carry-over section as default
            for y_pos, sec in section_y_positions:
                if y_pos <= table_y:
                    table_section = sec
                else:
                    break  # Don't use sections that come after the table

            for row_num, row in enumerate(extracted, start=1):
                if not row:
                    continue

                cells = [clean(str(c)) if c else "" for c in row]
                if not any(cells):
                    continue

                # Check if this row itself is a section heading
                joined = " ".join(cells).strip()
                if joined in SECTION_ORDER:
                    table_section = joined
                    current_section = joined  # Update carry-over section
                    continue

                # Skip header rows and summary rows
                jl = joined.lower()
                if "date" in jl and "description" in jl and "amount" in jl:
                    continue
                if jl.startswith("total ") or jl.startswith("summary "):
                    continue
                if "no activity" in jl:
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
                        "Page": page_num + 1,
                        "Table": table_num,
                        "Row": row_num,
                        "Section": table_section,
                        "Date": date,
                        "Description": desc,
                        "Amount": amount,
                    }
                )

    doc.close()

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

    return merged[["Date", "Merchant", "AmountParsed", "Section", "SourceFile"]].copy()


def extract_transactions_from_pdf(pdf_path: str) -> pd.DataFrame:
    """
    Extract transactions from PDF using PyMuPDF for tables and pdfplumber for text.

    PyMuPDF handles:
    - Purchases section
    - Fees section
    - Payments and Credits (if in table format)
    - Secured Account Transactions (if in table format)

    pdfplumber text parsing handles:
    - Payments and Credits (as fallback)
    - Secured Account Transactions (as fallback)
    """
    # Extract table-based transactions with PyMuPDF
    pymupdf_df = extract_pymupdf_tables(pdf_path)

    # Extract text-based transactions for sections PyMuPDF might miss
    text_df = extract_text_based_transactions(pdf_path)

    # Combine: use all PyMuPDF results + text results that PyMuPDF didn't find
    if not pymupdf_df.empty and not text_df.empty:
        # Create a set of PyMuPDF transactions for comparison
        pymupdf_set = set(tuple(x) for x in pymupdf_df[["Date", "Merchant", "AmountParsed"]].values)

        # Find text transactions that aren't in PyMuPDF results
        text_only = []
        for _, row in text_df.iterrows():
            key = (row["Date"], row["Merchant"], row["AmountParsed"])
            if key not in pymupdf_set:
                text_only.append(row)

        if text_only:
            text_only_df = pd.DataFrame(text_only)
            combined = pd.concat([pymupdf_df, text_only_df], ignore_index=True)
        else:
            combined = pymupdf_df
    elif not text_df.empty:
        combined = text_df
    else:
        combined = pymupdf_df

    if combined.empty:
        return combined

    # Fix section assignment based on transaction description patterns
    # Secured Account transactions are ONLY specific transfer/deposit types
    def correct_section(row):
        if is_secured_account_transaction(row["Merchant"]):
            return "Secured Account Transactions"
        # If currently labeled as Secured Account but doesn't match patterns,
        # it's likely a Purchase that appeared in that section on the PDF
        elif row["Section"] == "Secured Account Transactions":
            return "Purchases"
        else:
            return row["Section"]

    combined["Section"] = combined.apply(correct_section, axis=1)

    return combined
