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


# Fallback ASCII-only -- mismo motivo que los marcadores [OK]/[FAIL]/[WARN] de abajo: una
# consola clásica de Windows (cp1252, sin Windows Terminal) truena con UnicodeEncodeError
# en los bloques Unicode (█ ╔ ╗ ░ ▄ etc.) del banner "de lujo". Este es el que ve cualquiera
# que instale Meridian en una terminal que no declare encoding UTF-8.
BANNER_ASCII = r"""[bold cyan]
 __  __           _     _ _
|  \/  | ___ _ __(_) __| (_) __ _ _ __
| |\/| |/ _ \ '__| |/ _` | |/ _` | '_ \
| |  | |  __/ |  | | (_| | | (_| | | | |
|_|  |_|\___|_|  |_|\__,_|_|\__,_|_| |_|
[/bold cyan][dim]codename: Project Foreman[/dim]"""

# Banner "de lujo" -- fuente de bloque (mismo estilo que un banner ANSI Shadow de figlet),
# a pedido de Rodrigo, con los colores de su tema real de terminal (oh-my-posh
# "kushal.omp.json": cian #00C7FC; su perfil de PowerShell: indigo #5C6BAF) y su propio
# mapache ASCII (de Documents/PowerShell/Microsoft.PowerShell_profile.ps1), reutilizado
# aquí tal cual con su permiso. Solo se muestra si la terminal declara un encoding UTF-8
# (ver `_supports_unicode_banner`).
BANNER_FANCY = (
    "[#5C6BAF]"
    "███╗   ███╗███████╗██████╗ ██╗██████╗ ██╗ █████╗ ███╗   ██╗\n"
    "████╗ ████║██╔════╝██╔══██╗██║██╔══██╗██║██╔══██╗████╗  ██║\n"
    "██╔████╔██║█████╗  ██████╔╝██║██║  ██║██║███████║██╔██╗ ██║\n"
    "██║╚██╔╝██║██╔══╝  ██╔══██╗██║██║  ██║██║██╔══██║██║╚██╗██║\n"
    "██║ ╚═╝ ██║███████╗██║  ██║██║██████╔╝██║██║  ██║██║ ╚████║\n"
    "╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚═╝╚═════╝ ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝"
    "[/]\n"
    "[#00C7FC]codename: Project Foreman[/]\n"
    "[#5C6BAF]"
    "░░░░░░░░░░░░░░░▄▄▄▄▄▄▄▄░░░░░░░░░░░░░░\n"
    "░▄█▀███▄▄████████████████████▄▄███▀█░\n"
    "░█░░▀████████████████████████████░░█░\n"
    "░░█▄░░▀████████████████████████░░░▄▀░\n"
    "░░░▀█▄▄████▀▀▀░░░░██░░░▀▀▀█████▄▄█▀░░\n"
    "░░░▄███▀▀░░░░░░░░░██░░░░░░░░░▀███▄░░░\n"
    "░░▄██▀░░░░░▄▄▄██▄▄██░▄██▄▄▄░░░░░▀██▄░\n"
    "▄██▀░░░▄▄▄███▄██████████▄███▄▄▄░░░▀█▄\n"
    "▀██▄▄██████████▀░███▀▀▀█████████▄▄▄█▀\n"
    "░░▀██████████▀░░░███░░░▀███████████▀░\n"
    "░░░░▀▀▀██████░░░█████▄░░▀██████▀▀░░░░\n"
    "░░░░░░░░░▀▀▀▀▄░░█████▀░▄█▀▀▀░░░░░░░░░\n"
    "░░░░░░░░░░░░░░▀▀▄▄▄▄▄▀▀░░░░░░░░░░░░░░"
    "[/]"
)


def _supports_unicode_banner() -> bool:
    encoding = (getattr(console.file, "encoding", "") or "").lower()
    return "utf" in encoding


def print_banner() -> None:
    console.print(BANNER_FANCY if _supports_unicode_banner() else BANNER_ASCII)
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
