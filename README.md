# Varo to Monarch

Convert Varo Bank PDF statements to Monarch Money CSV format. No more manual
data entry — point the tool at your Varo statements and get a Monarch-ready CSV
in seconds.

## Features

- 🖥️ **User-Friendly GUI**: Graphical interface for non-technical users (also
  available as standalone executables)
- 📄 **Hybrid PDF Extraction**: Uses PyMuPDF for table-based extraction and
  pdfplumber for text-based parsing to capture all transactions, including
  multi-line descriptions that span page boundaries
- 🔄 **Parallel Processing**: Process multiple PDFs concurrently with
  configurable worker count
- 📊 **Progress Tracking**: Rich progress bars with per-file status
- 💰 **Smart Amount Handling**: Automatically applies correct sign per section
  (purchases negative, payments positive, etc.)
- 🎯 **Intelligent Section Detection**: Identifies and categorises Purchases,
  Payments/Credits, Fees, and Secured Account transactions
- 🏦 **Account Mapping**: Maps transactions to the correct account (Varo Believe
  Card vs Varo Secured Account)
- 🏷️ **Auto-Categorization**: Secured Account transactions are automatically
  tagged as `Transfer` in the Category column; credit card transactions are left
  uncategorized for Monarch to classify
- 📊 **Account Summary**: After each run the tool prints the exact balance and
  limit values to enter when creating accounts in Monarch Money
- 📝 **Monarch-Ready Output**: CSV with the exact columns Monarch Money expects

## Installation

### Option 1: Standalone Executable (Recommended for Non-Technical Users)

Download the pre-built executable for your OS from the
[Releases page](https://github.com/blacksuan19/varo-to-monarch/releases):

- **Windows**: `varo-to-monarch-windows.exe`
- **macOS**: `varo-to-monarch-macos.app.zip` (extract and run)
- **Linux**: `varo-to-monarch-linux`

No installation required — just download and run.

### Option 2: Install via pip

```bash
pip install varo-to-monarch
```

### Option 3: From Source

```bash
git clone https://github.com/blacksuan19/varo-to-monarch.git
cd varo-to-monarch
pip install .
```

## Usage

### GUI

**Standalone executable:** double-click the downloaded file.

**Installed package:**

```bash
vtm-gui
```

The GUI lets you:

1. Select the folder containing your Varo PDF statements
2. Choose the output CSV path (defaults to `varo_monarch_combined.csv` in the
   input folder)
3. Optionally set a filename pattern, worker count, and whether to include the
   source filename column

Click **Convert to Monarch CSV** and watch the progress bar. Once complete, an
**Account Summary** panel appears showing the exact balance and limit values to
enter when creating accounts in Monarch Money.

### CLI

**Basic usage** — convert all PDFs in a folder:

```bash
vtm path/to/statements
```

Output is written to `path/to/statements/varo_monarch_combined.csv` by default.
An account summary is printed after each run showing the exact values to enter
when creating accounts in Monarch Money.

**All options:**

```
vtm [OPTIONS] [FOLDER]

Arguments:
  FOLDER  Directory containing Varo PDF statements

Options:
  -o, --output PATH               Output CSV file path
  -p, --pattern TEXT              Glob pattern for PDFs (default: *.pdf)
  -w, --workers INT               Parallel workers (default: auto)
      --include-file-names /
      --no-include-file-names     Include/exclude SourceFile column (default: include)
  -h, --help                      Show this message and exit
```

**Examples:**

```bash
# Custom output path
vtm ./statements --output ~/monarch_import.csv

# Process only a specific statement
vtm ./statements --pattern "2025-12.pdf"

# Use 4 parallel workers
vtm ./statements --workers 4

# Omit the source filename column from output
vtm ./statements --no-include-file-names
```

## Output Format

| Column          | Description                                                        |
| --------------- | ------------------------------------------------------------------ |
| `Date`          | Transaction date (`MM/DD/YYYY`)                                    |
| `Merchant Name` | Full transaction description                                       |
| `Category`      | `Transfer` for Secured Account transactions; empty for credit card |
| `Account`       | `Varo Believe Card` or `Varo Secured Account`                      |
| `Amount`        | Signed amount (negative = debit, positive = credit)                |
| `SourceFile`    | Source PDF filename (omitted with `--no-include-file-names`)       |

## Importing into Monarch Money

> **Note:** CSV imports are available on **web only** (not the mobile app) and
> **cannot be undone**. Test with a smaller file first if you're unsure. See
> [Monarch's full import guide](https://help.monarch.com/hc/en-us/articles/4409682789908-Importing-Transaction-History-Manually)
> for reference.

1. On the Monarch web app, go to **Accounts** and click **+ Add Account**.
2. Click **"Import transaction & balance history"**, then **"Import
   transactions"**.
3. Upload the generated CSV file.
4. Monarch will auto-detect the column mappings (Date, Merchant Name, Account,
   Amount) — confirm them and proceed.
5. On the **"Assign CSV accounts to Monarch accounts"** screen you'll see two
   entries. For each one, open the dropdown and choose **"Create a new
   account"** with the appropriate type:

   | CSV Account            | Account type to create      | Balance / Limit                                                                     |
   | ---------------------- | --------------------------- | ----------------------------------------------------------------------------------- |
   | `Varo Believe Card`    | **Credit Card**             | Current balance and credit limit — shown in the Account Summary printed by the tool |
   | `Varo Secured Account` | **Checking** or **Savings** | Balance — shown in the Account Summary printed by the tool                          |

6. Choose how to handle overlapping transactions:
   - **Prioritize CSV** — replaces any existing transactions in the date range
   - **Prioritize Monarch** — keeps existing data, only imports earlier missing
     ones
   - **Import all** — imports everything, may create duplicates

7. Review the summary and click **Import transactions** to finish.

> **Tip:** On repeat imports, select the existing Monarch accounts instead of
> creating new ones to avoid duplicates.

## How It Works

The tool uses a two-pass hybrid extraction strategy:

1. **Table extraction (PyMuPDF)** — detects and extracts transaction tables
   directly from the PDF structure. Handles Purchases, Fees, Payments and
   Credits, and Secured Account Transactions sections.

2. **Text parsing (pdfplumber)** — line-by-line fallback for transactions that
   table detection misses. All pages are flattened into a single line list
   before parsing so that multi-line descriptions split across page boundaries
   are correctly merged.

3. **Deduplication** — results from both passes are merged; rows already
   captured by table extraction are not duplicated from the text pass.

4. **Section-based classification** — each transaction is assigned the correct
   account and amount sign based on which section it appears in:

   | Section                      | Sign     | Account              |
   | ---------------------------- | -------- | -------------------- |
   | Purchases                    | negative | Varo Believe Card    |
   | Fees                         | negative | Varo Believe Card    |
   | Payments and Credits         | positive | Varo Believe Card    |
   | Secured Account Transactions | from PDF | Varo Secured Account |

5. **Post-processing** — description-based rules override section assignments
   where needed (e.g. transfer descriptions always go to Varo Secured Account
   regardless of which table they appear in).

## Supported Transaction Types

### Varo Believe Card

- Credit card purchases
- Fees and charges
- Payments and credits

### Varo Secured Account

- Transfers from Secured Account to Believe Card
  (`Trf from Vault to Charge C Bal`)
- Transfers from Secured Account to Checking (`Transfer from Vault to DDA`)
- Deposits into Secured Account (`Move Your Pay - Chk to Believe`)

## Requirements

- Python 3.8 or higher

## Troubleshooting

**No transactions extracted:**

- Make sure the PDFs are genuine Varo Bank statements
- Check that the files are not password-protected or corrupted

**Missing transactions:**

- The tool handles multi-page statements automatically
- Try `--workers 1` to rule out any concurrency issues

**Wrong amounts or accounts:**

- Open an issue on GitHub with a redacted sample statement

## Development

```bash
# Clone and install
git clone https://github.com/blacksuan19/varo-to-monarch.git
cd varo-to-monarch
pip install -e .

# Version bump
bumpver update --patch   # 0.4.0 → 0.4.1
bumpver update --minor   # 0.4.0 → 0.5.0
```

## Contributing

Contributions are welcome! Please submit a Pull Request.

## License

GNU General Public License v3 — see [LICENSE](LICENSE) for details.

## Disclaimer

This tool is not affiliated with, endorsed by, or connected to Varo Bank or
Monarch Money. Use at your own risk. Always verify converted data before
importing into Monarch Money.
