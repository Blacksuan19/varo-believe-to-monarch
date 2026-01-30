# Varo to Monarch

Convert Varo Bank PDF statements to Monarch Money CSV format with ease. No more
manual data entry - just point the tool at your Varo statements and get a
Monarch-ready CSV file in seconds.

## Features

- �️ **User-Friendly GUI**: Easy-to-use graphical interface for non-technical
  users (also available as standalone executables for Windows, macOS, and Linux)
- �📄 **Hybrid PDF Extraction**: Uses PyMuPDF for table-based extraction and
  pdfplumber for text-based parsing to capture all transactions
- 🔄 **Parallel Processing**: Process multiple PDFs concurrently with
  customizable worker count for faster conversions
- 📊 **Progress Tracking**: Rich progress bars show real-time conversion status
  for each file
- 💰 **Smart Amount Handling**: Automatically applies correct sign
  transformations per transaction section (purchases are negative, payments are
  positive, etc.)
- 🎯 **Intelligent Section Detection**: Accurately identifies and categorizes
  Purchases, Payments/Credits, Fees, and Secured Account transactions
- 🏦 **Account Mapping**: Automatically maps transactions to correct accounts
  (Varo Believe Card vs Varo Secured Account)
- 📝 **Monarch-Ready Output**: Generates CSV files with the exact format
  required by Monarch Money import
- 🚀 **No External Dependencies**: Pure Python implementation with no system
  dependencies required

## Installation

### Option 1: Standalone Executable (Recommended for Non-Technical Users)

Download the pre-built executable for your operating system from the
[Releases page](https://github.com/blacksuan19/varo-to-monarch/releases):

- **Windows**: `varo-to-monarch-windows.exe`
- **macOS**: `varo-to-monarch-macos.app.zip` (extract and run)
- **Linux**: `varo-to-monarch-linux`

No installation required - just download and run!

### Option 2: Install via pip (For Developers/CLI Users)

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

### Graphical User Interface (GUI)

**Using the standalone executable:**

Simply double-click the downloaded executable file.

**Using the installed package:**

```bash
vtm-gui
```

The GUI provides:

1. **Folder selection**: Browse to select your folder containing Varo PDF
   statements
2. **Output file selection**: Choose where to save the output CSV (defaults to
   `varo_monarch_combined.csv` in the input folder)
3. **Advanced options** (optional):
   - File pattern filter (e.g., `2024*.pdf` to process only 2024 statements)
   - Number of parallel workers for faster processing
   - Option to include/exclude source file names in the output

Click **Convert to Monarch CSV** and watch the progress bar as your statements
are processed!

### Command Line Interface (CLI)

**Basic Usage** - Convert all PDFs in a folder:

```bash
vtm path/to/statements
```

This will:

1. Find all PDF files in the specified directory
2. Extract transactions from each statement
3. Combine them into a single CSV file:
   `path/to/statements/varo_monarch_combined.csv`

### Advanced Options

**Custom output file:**

```bash
vtm path/to/statements --output path/to/output.csv
```

**Filter specific PDFs:**

```bash
vtm path/to/statements --pattern "2024*.pdf"
```

**Parallel processing (faster for multiple files):**

```bash
vtm path/to/statements --workers 4
```

**Exclude source filename column:**

```bash
vtm path/to/statements --no-include-file-names
```

**Get help:**

```bash
vtm --help
```

### Which Interface Should I Use?

- **Use the GUI** if you prefer a visual interface or are not comfortable with
  command-line tools
- **Use the CLI** if you want to automate conversions, integrate with scripts,
  or prefer terminal-based workflows

## Output Format

The generated CSV contains the following columns:

- **Date**: Transaction date (MM/DD/YYYY format)
- **Merchant Name**: Transaction description
- **Account**: Either "Varo Believe Card" or "Varo Secured Account"
- **Amount**: Transaction amount (negative for purchases/fees, positive for
  payments/credits)
- **SourceFile**: Original PDF filename (optional, can be excluded with
  `--no-include-file-names` in CLI or unchecked in GUI)

## How It Works

The tool uses a hybrid extraction strategy:

1. **Table Extraction (PyMuPDF)**: Detects and extracts transaction tables for
   structured data
2. **Text Parsing (pdfplumber)**: Fallback method for transactions that table
   detection misses
3. **Smart Deduplication**: Removes duplicate extractions while preserving
   legitimate duplicate transactions
4. **Section-Based Classification**: Assigns correct account and sign based on
   transaction type:
   - **Purchases**: Negative amounts → Varo Believe Card
   - **Fees**: Negative amounts → Varo Believe Card
   - **Payments and Credits**: Positive amounts → Varo Believe Card
   - **Secured Account Transactions**: Based on description patterns → Varo
     Secured Account

## Supported Transaction Types

### Varo Believe Card

- Credit card purchases
- Fees and charges
- Payments and credits

### Varo Secured Account

- Transfers from Secured Account to Believe Card
- Transfers from Secured Account to Checking Account (DDA)
- Deposits into Secured Account (e.g., "Move Your Pay")

## Requirements

- Python 3.8 or higher
- Internet connection for initial package installation

## Troubleshooting

**No transactions extracted:**

- Ensure your PDFs are actual Varo Bank statements
- Check that PDFs are not password-protected or corrupted

**Missing some transactions:**

- The tool automatically handles multi-page statements
- Try running with `--workers 1` to rule out concurrency issues

**Incorrect amounts or accounts:**

- File an issue on GitHub with a sample (redacted) statement

## Development

```bash
# Clone the repository
git clone https://github.com/blacksuan19/varo-to-monarch.git
cd varo-to-monarch

# Install in development mode
pip install -e .

# Build package
python -m build
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the GNU General Public License 3 - see the
LICENSE file for details.

## Disclaimer

This tool is not affiliated with, endorsed by, or connected to Varo Bank or
Monarch Money. Use at your own risk. Always verify the accuracy of converted
data before importing into Monarch Money.
