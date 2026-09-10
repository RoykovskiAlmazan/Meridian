from uuid import UUID

import typer

from meridian.cli.console import fail, ok, print_record
from meridian.identity import repository
from meridian.llm.registry import get_provider_for_subagent

app = typer.Typer(help="Conecta un subagente a un proveedor de IA (Claude, GPT, Gemini, Groq, Grok) para que pueda generar texto -- opcional, un subagente funciona sin esto, solo con menos capacidad.")


@app.command(
    "set",
    help="Conecta un subagente a un proveedor/modelo LLM. Necesitas primero guardar la API key con `meridianctl secrets put` y pasar aquí el credential_ref que te devolvió.",
    epilog=(
        "Ejemplo:\n\n"
        "  meridianctl secrets put --path llm/anthropic --field api_key\n"
        "  meridianctl llm set --subagent 88fc9c58-... --provider anthropic \\\n"
        "    --model claude-sonnet-5 --credential-ref vault:secret/llm/anthropic#api_key"
    ),
)
def set_(
    subagent: str = typer.Option(..., "--subagent"),
    provider: str = typer.Option(..., "--provider", help="anthropic | openai | gemini | groq | xai"),
    model: str = typer.Option(..., "--model", help="ej. claude-sonnet-5 (anthropic), gpt-4.1 (openai), gemini-2.0-flash (gemini), llama-3.3-70b-versatile (groq), grok-2 (xai)"),
    credential_ref: str = typer.Option(..., "--credential-ref", help="de `meridianctl secrets put`"),
) -> None:
    repository.set_subagent_llm_config(UUID(subagent), provider, model, credential_ref)
    ok(f"subagent={subagent} -> provider={provider} model={model}")


@app.command(
    "get",
    epilog="Ejemplo:\n\n  meridianctl llm get --subagent 88fc9c58-...",
)
def get(subagent: str = typer.Option(..., "--subagent")) -> None:
    config = repository.get_subagent_llm_config(UUID(subagent))
    if config is None:
        typer.echo("sin configurar")
    else:
        print_record(config)


@app.command(
    "test",
    epilog="Ejemplo:\n\n  meridianctl llm test --subagent 88fc9c58-... --prompt \"Resume en una palabra: Meridian\"",
)
def test(
    subagent: str = typer.Option(..., "--subagent"),
    prompt: str = typer.Option("Responde con una sola palabra: 'ok'.", "--prompt"),
) -> None:
    """Llamada real al proveedor configurado, para confirmar que la credencial y el
    modelo funcionan antes de conectarlo a un subagente en producción."""
    provider = get_provider_for_subagent(subagent)
    if provider is None:
        fail("este subagente no tiene un proveedor LLM configurado (`meridianctl llm set`)")
        raise typer.Exit(code=1)
    response = provider.complete(system=None, prompt=prompt, max_tokens=64)
    ok(f"[{response.provider}/{response.model}] {response.text!r}")
    typer.echo(f"tokens: input={response.input_tokens} output={response.output_tokens}")
