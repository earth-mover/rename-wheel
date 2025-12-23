"""Command-line interface for wheel-rename."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from wheel_rename.download import download_compatible_wheel, list_wheels
from wheel_rename.rename import inspect_wheel, rename_wheel

console = Console()
err_console = Console(stderr=True)


@click.group()
@click.version_option()
def main() -> None:
    """Rename Python wheel packages for multi-version installation."""
    pass


@main.command()
@click.argument("wheel_path", type=click.Path(exists=True, path_type=Path))
@click.argument("new_name")
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    help="Output directory for the renamed wheel (default: same as input)",
)
@click.option(
    "--no-update-imports",
    is_flag=True,
    default=False,
    help="Do not update import statements in Python files",
)
def rename(
    wheel_path: Path,
    new_name: str,
    output: Path | None,
    no_update_imports: bool,
) -> None:
    """Rename a wheel package.

    WHEEL_PATH: Path to the wheel file to rename
    NEW_NAME: New package name (e.g., "icechunk_v1")
    """
    try:
        with console.status(f"[bold blue]Renaming {wheel_path.name}..."):
            result = rename_wheel(
                wheel_path,
                new_name,
                output_dir=output,
                update_imports=not no_update_imports,
            )

        console.print(f"[green]✓[/green] Created: [bold]{result}[/bold]")

    except Exception as e:
        err_console.print(f"[red]✗ Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument("wheel_path", type=click.Path(exists=True, path_type=Path))
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def inspect(wheel_path: Path, as_json: bool) -> None:
    """Inspect a wheel's structure.

    WHEEL_PATH: Path to the wheel file to inspect
    """
    try:
        info = inspect_wheel(wheel_path)

        if as_json:
            click.echo(json.dumps(info, indent=2))
        else:
            # Create info table
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column("Key", style="dim")
            table.add_column("Value", style="bold")

            table.add_row("Wheel", str(info["filename"]))
            table.add_row("Distribution", str(info["distribution"]))
            table.add_row("Version", str(info["version"]))
            table.add_row("Python", str(info["python_tag"]))
            table.add_row("ABI", str(info["abi_tag"]))
            table.add_row("Platform", str(info["platform_tag"]))

            console.print(Panel(table, title="[bold]Wheel Info[/bold]", border_style="blue"))

            extensions = info.get("extensions", [])
            if extensions:
                assert isinstance(extensions, list)

                ext_table = Table(show_header=True, header_style="bold")
                ext_table.add_column("Extension", style="cyan")
                ext_table.add_column("Renamable", justify="center")

                for ext in extensions:
                    assert isinstance(ext, dict)
                    if ext.get("has_underscore_prefix") == "True":
                        status = "[green]✓ Yes[/green]"
                    else:
                        status = "[red]✗ No[/red]"
                    ext_table.add_row(ext["path"], status)

                console.print(ext_table)
                console.print()

                if info.get("has_underscore_prefix_extension"):
                    console.print(
                        Panel(
                            "[green]This wheel uses underscore-prefix extensions.\n"
                            "Renaming should work correctly.[/green]",
                            title="[bold green]✓ Safe to Rename[/bold green]",
                            border_style="green",
                        )
                    )
                else:
                    console.print(
                        Panel(
                            "[yellow]This wheel has extensions without underscore prefix.\n"
                            "Renaming may cause import errors.\n"
                            "Consider rebuilding from source instead.[/yellow]",
                            title="[bold yellow]⚠ Warning[/bold yellow]",
                            border_style="yellow",
                        )
                    )
            else:
                console.print(
                    Panel(
                        "[green]No compiled extensions found (pure Python wheel).\n"
                        "Renaming should work correctly.[/green]",
                        title="[bold green]✓ Safe to Rename[/bold green]",
                        border_style="green",
                    )
                )

    except Exception as e:
        err_console.print(f"[red]✗ Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument("package")
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=Path(),
    help="Output directory for the downloaded wheel (default: current directory)",
)
@click.option(
    "-i",
    "--index-url",
    default="https://pypi.org/simple/",
    help="Base URL of the package index (default: PyPI)",
)
@click.option(
    "--version",
    "pkg_version",
    default=None,
    help="PEP 440 version specifier (e.g., '==1.0.0', '<2', '>=1.0,<2')",
)
@click.option(
    "--list",
    "list_only",
    is_flag=True,
    help="List available wheels without downloading",
)
def download(
    package: str,
    output: Path,
    index_url: str,
    pkg_version: str | None,
    list_only: bool,
) -> None:
    """Download a compatible wheel from a package index.

    PACKAGE: Name of the package to download

    Examples:

        wheel-rename download numpy -o ./wheels/

        wheel-rename download icechunk -i https://pypi.anaconda.org/scientific-python-nightly-wheels/simple

        wheel-rename download requests --list
    """
    try:
        if list_only:
            from packaging.version import Version

            with console.status(f"[bold blue]Fetching wheel list for {package}..."):
                wheels = list_wheels(package, index_url)

            if not wheels:
                err_console.print(f"[red]✗[/red] No wheels found for [bold]{package}[/bold]")
                sys.exit(1)

            table = Table(title=f"Available wheels for [bold]{package}[/bold]")
            table.add_column("Filename", style="cyan")
            table.add_column("Version", style="green")

            for wheel in sorted(
                wheels,
                key=lambda w: Version(w.version) if w.version else Version("0"),
                reverse=True,
            ):
                table.add_row(wheel.filename, wheel.version or "unknown")

            console.print(table)
        else:
            with console.status(f"[bold blue]Finding compatible wheel for {package}..."):
                result = download_compatible_wheel(
                    package,
                    output,
                    index_url=index_url,
                    version=pkg_version,
                    show_progress=False,  # We use rich status instead
                )

            if result is None:
                err_console.print(
                    f"[red]✗[/red] No compatible wheel found for [bold]{package}[/bold]"
                )
                sys.exit(1)

            console.print(f"[green]✓[/green] Downloaded: [bold]{result}[/bold]")

    except Exception as e:
        err_console.print(f"[red]✗ Error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
