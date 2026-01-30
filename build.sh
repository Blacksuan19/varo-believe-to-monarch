#!/bin/bash
# Build the package, then run tests.

set -e

echo "🧹 Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info varo_to_monarch.egg-info

echo "📦 Building package..."
python -m build

echo "🧪 Running tests..."
python -c "import typer" 2>/dev/null || {
	echo "";
	echo "Missing runtime deps in this environment.";
	echo "Run: pip install -e '.[dev]'   (or: pip install '.[dev]')";
	exit 1;
}
pytest

