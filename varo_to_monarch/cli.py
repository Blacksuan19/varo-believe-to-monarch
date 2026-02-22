"""Command Line Interface."""

from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import click
import pandas as pd
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from .extractors import extract_account_summary, extract_transactions_from_pdf
from .processing import finalize_monarch
from .utils import default_workers, find_pdfs, latest_pdf_by_date

app = typer.Typer(
    help="Convert Varo Believe credit card statements to Monarch CSV.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


def _print_account_summary(con: Console, summary: dict, source_name: str) -> None:
    """Print a Rich panel showing account balances for Monarch account creation."""
    b = summary["believe"]
    s = summary["secured"]

    acct = f" ({b['account_number']})" if b.get("account_number") else ""
    ending = s.get("ending_balance", "")

    tbl = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    tbl.add_column("Account", style="bold")
    tbl.add_column("Monarch type")
    tbl.add_column("Field", style="dim")
    tbl.add_column("Value", style="green")

    # Believe Card rows
    tbl.add_row(
        f"Varo Believe Card{acct}",
        "Credit Card",
        "Current Balance",
        f"${b.get('new_balance', '?')}",
    )
    tbl.add_row("", "", "Credit Limit", f"${ending or '?'} (= Secured ending balance)")
    if b.get("payment_due_amount") and b.get("payment_due_date"):
        tbl.add_row(
            "",
            "",
            "Payment Due",
            f"${b['payment_due_amount']} by {b['payment_due_date']}",
        )

    tbl.add_section()

    # Secured Account rows
    tbl.add_row(
        "Varo Secured Account",
        "Checking / Savings",
        "Balance",
        f"${ending or '?'}",
    )

    con.print()
    con.print(
        Panel(
            tbl,
            title=f"[bold]Account Summary[/bold] [dim]({source_name})[/dim]",
            subtitle="[dim]Use these values when adding accounts in Monarch Money[/dim]",
            border_style="cyan",
        )
    )


@app.command()
def convert(
    folder: Optional[Path] = typer.Argument(
        None, exists=True, file_okay=False, dir_okay=True, resolve_path=True
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    pattern: str = typer.Option("*.pdf", "--pattern", "-p"),
    workers: int = typer.Option(default_workers(), "--workers", "-w", min=1),
    include_file_names: bool = typer.Option(
        True,
        "--include-file-names/--no-include-file-names",
    ),
):
    """Convert Varo Believe credit card PDF statements to Monarch Money CSV format.

    Args:
        folder: Directory containing Varo Believe PDF statements
        output: Output CSV file path (default: <folder>/varo_monarch_combined.csv)
        pattern: Glob pattern for PDF files (default: *.pdf)
        workers: Number of parallel workers (default: auto-detect)
        include_file_names: Include file names column in output CSV
    """
    console.print("[dim]🔒 100% offline — your data never leaves this machine[/dim]")

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
    result = finalize_monarch(combined, include_file_names)

    if result.empty:
        console.print("[red]No transactions extracted[/red]")
        raise typer.Exit(2)

    result.to_csv(out_csv, index=False)
    console.print(f"[bold green]✓ {len(result)} transactions → {out_csv}[/bold green]")

    # Show account summary from the PDF with the most recent transactions.
    latest_pdf = latest_pdf_by_date(combined, pdfs)
    summary = extract_account_summary(str(latest_pdf))
    if summary:
        _print_account_summary(console, summary, latest_pdf.name)

    if failures:
        console.print(f"[yellow]{len(failures)} file(s) failed[/yellow]")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
