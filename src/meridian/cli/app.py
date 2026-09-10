"""meridianctl: punto de entrada único de la CLI de administración de Meridian.

Ver docs/design/0002-repo-structure-and-cli.md para el catálogo completo de comandos.
"""
import typer

from meridian.cli.commands import (
    allow,
    approvals,
    audit,
    bus,
    config,
    cron,
    dev,
    doctor,
    gateway,
    init,
    llm,
    policy,
    results,
    secrets,
    subagent,
    tenant,
    vault,
)
from meridian.cli.console import get_version, print_banner

app = typer.Typer(
    help="meridianctl -- administra Meridian: crea tus identidades (tenant, gateway, subagente), autorízalas, y revisa qué está pasando. Corre `meridianctl init` si es tu primera vez.",
    epilog=(
        "Primeros pasos (una vez que ya corriste `meridianctl init` y `meridianctl doctor`\n"
        "salió en verde):\n\n"
        "  1. meridianctl tenant create --name mi-organizacion\n"
        "     -> tu organización dentro de Meridian, todo lo demás vive dentro de un tenant\n\n"
        "  2. meridianctl gateway create --tenant <tenant_id> --type cron --name mi-gateway\n"
        "     -> la vía por la que van a entrar las instrucciones (aquí: un horario)\n\n"
        "  3. meridianctl subagent create --tenant <tenant_id> --name mi-tarea --domain lo-que-sea\n"
        "     -> el trabajador que va a ejecutar algo (tú programas qué hace)\n\n"
        "  4. meridianctl allow set --gateway <gateway_id> --subagent <subagent_id> --intents mi_dominio.mi_accion\n"
        "     -> sin este permiso explícito, el gateway no puede pedirle nada al subagente\n\n"
        "  5. meridianctl cron create --tenant <tenant_id> --gateway <gateway_id> \\\n"
        "       --name mi-job --schedule '@hourly' --intent-type mi_dominio.mi_accion --subagents <subagent_id>\n"
        "     -> y ya queda disparándose solo\n\n"
        "Cada paso tiene su propio ejemplo en `meridianctl <comando> --help` "
        "(ej. `meridianctl tenant create --help`). Para el detalle completo, ver README.md."
    ),
    no_args_is_help=False,
    invoke_without_command=True,
)

app.command(
    "init",
    help="Wizard de instalación: .env + infra + Vault init, en un solo paso.",
    epilog="Ejemplo:\n\n  meridianctl init\n  meridianctl init --subagents   # + sample_subagent_a/b",
)(init.init)
app.add_typer(dev.app, name="dev")
app.add_typer(config.app, name="config")
app.command(
    "doctor",
    help="Diagnóstico de salud de la instalación (Docker, Postgres, Redis, Vault, schema), con --fix para autoreparar lo seguro.",
    epilog="Ejemplos:\n\n  meridianctl doctor\n  meridianctl doctor --fix",
)(doctor.doctor)
app.add_typer(tenant.app, name="tenant")
app.add_typer(gateway.app, name="gateway")
app.add_typer(subagent.app, name="subagent")
app.add_typer(allow.app, name="allow")
app.add_typer(policy.app, name="policy")
app.add_typer(approvals.app, name="approvals")
app.add_typer(cron.app, name="cron")
app.add_typer(secrets.app, name="secrets")
app.add_typer(llm.app, name="llm")
app.add_typer(audit.app, name="audit")
app.add_typer(results.app, name="results")
app.add_typer(bus.app, name="bus")
app.add_typer(vault.app, name="vault")


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
