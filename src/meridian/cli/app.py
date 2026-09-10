"""meridianctl: punto de entrada único de la CLI de administración de Meridian.

Ver docs/design/0002-repo-structure-and-cli.md para el catálogo completo de comandos.
"""
import typer

from meridian.cli.commands import allow, audit, bus, config, cron, dev, doctor, gateway, llm, policy, secrets, subagent, tenant
from meridian.cli.console import get_version, print_banner

app = typer.Typer(
    help="meridianctl -- administración de la plataforma Meridian.",
    no_args_is_help=False,
    invoke_without_command=True,
)

app.add_typer(dev.app, name="dev")
app.add_typer(config.app, name="config")
app.command("doctor", help="Diagnóstico de salud de la instalación (Docker, Postgres, Redis, Vault, schema), con --fix para autoreparar lo seguro.")(doctor.doctor)
app.add_typer(tenant.app, name="tenant")
app.add_typer(gateway.app, name="gateway")
app.add_typer(subagent.app, name="subagent")
app.add_typer(allow.app, name="allow")
app.add_typer(policy.app, name="policy")
app.add_typer(cron.app, name="cron")
app.add_typer(secrets.app, name="secrets")
app.add_typer(llm.app, name="llm")
app.add_typer(audit.app, name="audit")
app.add_typer(bus.app, name="bus")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(get_version())
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True, help="Muestra la versión y sale."),
) -> None:
    if ctx.invoked_subcommand is None:
        print_banner()
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
