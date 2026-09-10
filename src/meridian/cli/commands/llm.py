from uuid import UUID

import typer

from meridian.identity import repository
from meridian.llm.registry import get_provider_for_subagent

app = typer.Typer(help="Qué proveedor/modelo LLM usa cada subagente (configurable, multi-proveedor).")


@app.command("set")
def set_(
    subagent: str = typer.Option(..., "--subagent"),
    provider: str = typer.Option(..., "--provider", help="anthropic | openai | gemini"),
    model: str = typer.Option(..., "--model", help="ej. claude-sonnet-5 (anthropic) o gpt-4.1 (openai)"),
    credential_ref: str = typer.Option(..., "--credential-ref", help="de `meridianctl secrets put`"),
) -> None:
    repository.set_subagent_llm_config(UUID(subagent), provider, model, credential_ref)
    typer.echo(f"subagent={subagent} -> provider={provider} model={model}")


@app.command("get")
def get(subagent: str = typer.Option(..., "--subagent")) -> None:
    config = repository.get_subagent_llm_config(UUID(subagent))
    typer.echo(config or "sin configurar")


@app.command("test")
def test(
    subagent: str = typer.Option(..., "--subagent"),
    prompt: str = typer.Option("Responde con una sola palabra: 'ok'.", "--prompt"),
) -> None:
    """Llamada real al proveedor configurado, para confirmar que la credencial y el
    modelo funcionan antes de conectarlo a un subagente en producción."""
    provider = get_provider_for_subagent(subagent)
    if provider is None:
        typer.echo("este subagente no tiene un proveedor LLM configurado (`meridianctl llm set`)")
        raise typer.Exit(code=1)
    response = provider.complete(system=None, prompt=prompt, max_tokens=64)
    typer.echo(f"[{response.provider}/{response.model}] {response.text!r}")
    typer.echo(f"tokens: input={response.input_tokens} output={response.output_tokens}")
