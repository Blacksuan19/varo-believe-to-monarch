"""Command Line Interface."""

from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import click
import pandas as pd
import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .extractors import extract_transactions_from_pdf
from .processing import finalize_monarch
from .utils import default_workers, find_pdfs

app = typer.Typer(
    help="Convert Varo statements to Monarch CSV.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


@app.command()
def convert(
    folder: Optional[Path] = typer.Argument(
        None, exists=True, file_okay=False, dir_okay=True, resolve_path=True
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    pattern: str = typer.Option("*.pdf", "--pattern", "-p"),
    workers: int = typer.Option(default_workers(), "--workers", "-w", min=1),
    include_source_file: bool = typer.Option(
        True,
        "--include-source-file/--no-include-source-file",
    ),
):
    """Convert Varo Bank PDF statements to Monarch Money CSV format.

    Args:
        folder: Directory containing Varo PDF statements
        output: Output CSV file path (default: <folder>/varo_monarch_combined.csv)
        pattern: Glob pattern for PDF files (default: *.pdf)
        workers: Number of parallel workers (default: auto-detect)
        include_source_file: Include source filename column in output CSV
    """
    if folder is None:
        typer.echo(click.get_current_context().get_help())
        raise typer.Exit(0)

    out_csv = output or (folder / "varo_monarch_combined.csv")
    pdfs = find_pdfs(folder, pattern)
    if not pdfs:
        raise typer.BadParameter(f"No PDFs found matching '{pattern}' in {folder}")

    console.print(f"[bold]Found {len(pdfs)} PDF(s)[/bold]")
    console.print(f"Output: {out_csv}")

    frames: list[pd.DataFrame] = []
    failures: list[tuple[str, str]] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing PDFs...", total=len(pdfs))

        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(extract_transactions_from_pdf, str(p)): p for p in pdfs}
            for fut in as_completed(futs):
                p = futs[fut]
                try:
                    df = fut.result()
                    frames.append(df)
                    progress.console.print(f"✓ {p.name} → {len(df)} txns")
                except Exception as e:
                    failures.append((str(p), repr(e)))
                    progress.console.print(f"[red]✗ {p.name}: {e!r}[/red]")
                finally:
                    progress.advance(task)

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    result = finalize_monarch(combined, include_source_file)

    if result.empty:
        console.print("[red]No transactions extracted[/red]")
        raise typer.Exit(2)

    result.to_csv(out_csv, index=False)
    console.print(f"[bold green]✓ {len(result)} transactions → {out_csv}[/bold green]")

    if failures:
        console.print(f"[yellow]{len(failures)} file(s) failed[/yellow]")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
