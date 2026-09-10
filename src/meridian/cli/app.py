"""meridianctl: punto de entrada único de la CLI de administración de Meridian.

Ver docs/design/0002-repo-structure-and-cli.md para el catálogo completo de comandos.
"""
import typer

from meridian.cli.commands import allow, audit, bus, config, cron, dev, gateway, policy, subagent, tenant

app = typer.Typer(help="meridianctl -- administración de la plataforma Meridian.")

app.add_typer(dev.app, name="dev")
app.add_typer(config.app, name="config")
app.add_typer(tenant.app, name="tenant")
app.add_typer(gateway.app, name="gateway")
app.add_typer(subagent.app, name="subagent")
app.add_typer(allow.app, name="allow")
app.add_typer(policy.app, name="policy")
app.add_typer(cron.app, name="cron")
app.add_typer(audit.app, name="audit")
app.add_typer(bus.app, name="bus")


if __name__ == "__main__":
    app()
