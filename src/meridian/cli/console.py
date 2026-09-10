"""Estilo compartido de la CLI (`meridianctl`) -- banner, colores, tablas. Un único
`Console` de Rich para que toda la salida se vea consistente entre subcomandos."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version

from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


def get_version() -> str:
    try:
        return pkg_version("meridian")
    except PackageNotFoundError:
        return "0.0.0-dev"


BANNER = r"""[bold cyan]
 __  __           _     _ _
|  \/  | ___ _ __(_) __| (_) __ _ _ __
| |\/| |/ _ \ '__| |/ _` | |/ _` | '_ \
| |  | |  __/ |  | | (_| | | (_| | | | |
|_|  |_|\___|_|  |_|\__,_|_|\__,_|_| |_|
[/bold cyan][dim]codename: Project Foreman[/dim]"""


def print_banner() -> None:
    console.print(BANNER)
    console.print(f"[dim]v{get_version()} · beta · orquestación multiagente de propósito general[/dim]\n")



def ok(message: str) -> None:
    # Símbolos ASCII a propósito (no Unicode "✓"/"✗"): la consola clásica de Windows
    # (cp1252, sin Windows Terminal) truena con UnicodeEncodeError en caracteres fuera de
    # ese charset -- se comprobó en la práctica. ASCII funciona en cualquier terminal.
    console.print(f"[bold green][OK][/bold green]   {message}")


def fail(message: str) -> None:
    console.print(f"[bold red][FAIL][/bold red] {message}")


def warn(message: str) -> None:
    console.print(f"[bold yellow][WARN][/bold yellow] {message}")


def info(message: str) -> None:
    console.print(f"[dim]  -[/dim] {message}")


def new_table(*columns: str, title: str | None = None) -> Table:
    table = Table(title=title, show_lines=False, header_style="bold cyan")
    for col in columns:
        table.add_column(col)
    return table


def print_records(records: list[dict], title: str | None = None) -> None:
    """Tabla Rich a partir de una lista de dicts (lo que devuelven las funciones de
    `identity.repository`) -- reemplaza el `typer.echo(dict)` crudo de antes."""
    if not records:
        info("(sin resultados)")
        return
    columns = list(records[0].keys())
    table = new_table(*columns, title=title)
    for record in records:
        table.add_row(*(str(record.get(col, "")) for col in columns))
    console.print(table)


def print_record(record: dict, title: str | None = None) -> None:
    """Un solo registro como tabla clave/valor de dos columnas."""
    table = new_table("campo", "valor", title=title)
    for key, value in record.items():
        table.add_row(key, str(value))
    console.print(table)
