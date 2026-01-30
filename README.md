# Varo to Monarch

Convert Varo Bank PDF statements to Monarch Money CSV format with ease.

## Features

- 📄 **Hybrid PDF Extraction**: Uses Camelot for table-based extraction and
  pdfplumber for text-based parsing
- 🔄 **Parallel Processing**: Process multiple PDFs concurrently with
  customizable worker count
- 📊 **Progress Tracking**: Rich progress bars show real-time conversion status
- 💰 **Smart Amount Handling**: Automatically applies correct sign
  transformations per transaction section
- 🎯 **Section Detection**: Accurately identifies Purchases, Payments/Credits,
  Fees, and Secured Account transactions
- 📝 **Monarch-Ready Output**: Generates CSV files directly compatible with
  Monarch Money import

## Installation

### From PyPI (once published)

```bash
pip install varo-to-monarch
```

### From Source

````bash
# Varo to Monarch

Convert Varo PDF statements into a Monarch Money-compatible CSV.

## Install

From this repo:

```bash
python -m pip install .
````

(Once published to PyPI)

```bash
python -m pip install varo-to-monarch
```

## Run

Convert all PDFs in a folder:

```bash
varo-to-monarch ./statements
```

Common options:

```bash
varo-to-monarch ./statements --output ./varo_monarch_combined.csv
varo-to-monarch ./statements --pattern "*.pdf"
varo-to-monarch ./statements --workers 4
varo-to-monarch ./statements --no-include-source-file
```

See `varo-to-monarch --help` for all options.
