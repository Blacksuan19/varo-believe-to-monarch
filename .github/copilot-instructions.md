# Copilot Instructions: varo-to-monarch

## Project Purpose

CLI tool that converts Varo Bank PDF statements to Monarch Money-compatible CSV
format. Uses hybrid extraction strategy: PyMuPDF for table-based data and
pdfplumber for text-based parsing.

## Architecture Overview

**Entry Point**: [varo_to_monarch/cli.py](../varo_to_monarch/cli.py) - Typer CLI
with parallel processing via ProcessPoolExecutor

**Data Flow**:

1. PDF discovery → [utils.find_pdfs()](../varo_to_monarch/utils.py)
2. Parallel extraction →
   [extractors.extract_transactions_from_pdf()](../varo_to_monarch/extractors.py)
3. Post-processing →
   [processing.finalize_monarch()](../varo_to_monarch/processing.py)
4. CSV output with Monarch-compatible columns

**Dual Extraction Strategy** (critical pattern):

- **PyMuPDF** (find_tables): Handles "Purchases" and "Fees" sections
- **pdfplumber text parsing**: Handles "Payments and Credits" and "Secured
  Account Transactions" (sections where table extraction may be less reliable)
- Both strategies merge in `extract_transactions_from_pdf()` via `pd.concat()`

## Critical Patterns

### Section-Based Sign Logic

Transactions automatically apply correct positive/negative signs per section
(see [constants.SECTION_SIGN](../varo_to_monarch/constants.py)):

```python
SECTION_SIGN = {
    "Purchases": -1,      # force negative
    "Fees": -1,           # force negative
    "Payments and Credits": 1,  # force positive
    "Secured Account Transactions": 0,  # trust PDF sign
}
```

### Transaction Row Merging

Multi-row transactions (descriptions spanning rows) are merged using transaction
ID grouping:

- Group by `(SourceFile, Page, Table, Section)`
- Assign `TxnId` via cumulative sum of `IsTransactionStart`
- Aggregate: keep first valid date, concatenate descriptions, take first valid
  amount

### Amount Validation

Only process tokens with clear monetary indicators
([utils.parse_amount()](../varo_to_monarch/utils.py)):

- Must contain decimal point OR be wrapped in parentheses (negative)
- Avoid false positives (apartment numbers, street addresses)
- Strip `$`, handle parentheses as negative: `($12.34)` → `-12.34`

## Development Commands

```bash
# Install for development (environment managed by uv)
uv pip install .

# Build package
./build.sh  # Cleans previous builds, runs python -m build

# Version bump (uses bumpver)
bumpver update --patch  # 0.1.4 → 0.1.5

# Run locally
varo-to-monarch ./statements --workers 4 --output combined.csv

# Quick test with sample PDF
varo-to-monarch ./statements --pattern "7.pdf"
```

## Key Files

- [constants.py](../varo_to_monarch/constants.py): Section order, account
  mapping, sign rules
- [extractors.py](../varo_to_monarch/extractors.py): Core PDF parsing logic (287
  lines - review full file for context)
- [processing.py](../varo_to_monarch/processing.py): Post-processing, Monarch
  CSV formatting
- [pyproject.toml](../pyproject.toml): Dependencies (pymupdf, pandas,
  pdfplumber, typer, rich)

## Common Pitfalls

1. **PyMuPDF table detection**: Uses `find_tables()` method which automatically
   detects table structures
2. **Section detection order**: Must check
   [SECTION_ORDER](../varo_to_monarch/constants.py) sequentially as sections
   appear in PDF
3. **Date format consistency**: Always `MM/DD/YYYY`
   ([DATE_RE pattern](../varo_to_monarch/constants.py))
4. **Parallel processing**: Uses `ProcessPoolExecutor` not threads (needed for
   PDF parsing libraries)

## Testing Strategy

Test with real Varo PDF statements in [statements/](../statements/) directory
(includes `7.pdf` for testing). Focus on:

- Multi-section PDFs (all 4 transaction types)
- Multi-row descriptions
- Edge cases: parenthetical amounts, missing dollar signs, varied formatting
- Worker count variations (serial vs parallel)
