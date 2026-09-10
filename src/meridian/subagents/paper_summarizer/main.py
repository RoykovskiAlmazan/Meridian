"""Subagente 'paper_summarizer': busca en arXiv por la misma palabra clave que
'paper_search' y produce un resumen del abstract del resultado más relevante.

Si el subagente tiene un proveedor LLM configurado (`meridianctl llm set`), el resumen lo
genera ese LLM (multi-proveedor: Claude, OpenAI, etc. -- ver
docs/design/0009-llm-provider-layer.md). Si no, cae a un resumen EXTRACTIVO simple
(primeras oraciones del abstract) -- Meridian nunca deja de funcionar por no tener un LLM
configurado, solo degrada la calidad del resumen.

Uso: SUBAGENT_ID=<uuid> python -m meridian.subagents.paper_summarizer.main
"""
import os
import sys
from typing import Any

from meridian.llm.base import LLMProvider
from meridian.llm.registry import get_provider_for_subagent
from meridian.subagents import arxiv_client
from meridian.subagents.worker_base import run

_SYSTEM_PROMPT = (
    "Resume el abstract de un paper académico en un máximo de 3 oraciones, en español, "
    "directo y sin relleno. No inventes resultados que no estén en el abstract."
)


def _extractive_summary(abstract: str, max_sentences: int = 2) -> str:
    sentences = [s.strip() for s in abstract.replace("\n", " ").split(". ") if s.strip()]
    return ". ".join(sentences[:max_sentences]).rstrip(".") + "." if sentences else ""


def _llm_summary(provider: LLMProvider, abstract: str) -> tuple[str, str]:
    response = provider.complete(system=_SYSTEM_PROMPT, prompt=abstract, max_tokens=200)
    return response.text.strip(), f"llm:{response.provider}/{response.model}"


def make_handler(subagent_id: str):
    def handle(payload: dict[str, Any]) -> dict[str, Any]:
        query = payload["query"]
        results = arxiv_client.search(query, max_results=1)
        if not results:
            return {"query": query, "top_result": None, "summary": None}

        top = results[0]
        provider = get_provider_for_subagent(subagent_id)
        if provider is not None:
            summary, method = _llm_summary(provider, top["abstract"])
        else:
            summary, method = _extractive_summary(top["abstract"]), "extractive (sin LLM configurado)"

        return {
            "query": query,
            "top_result": {"title": top["title"], "url": top["url"]},
            "summary": summary,
            "summary_method": method,
        }

    return handle


def main() -> None:
    subagent_id = os.environ.get("SUBAGENT_ID")
    if not subagent_id:
        print("Falta SUBAGENT_ID en el entorno (uuid de subagents.id en Postgres)", file=sys.stderr)
        raise SystemExit(1)
    run(subagent_id, make_handler(subagent_id))


if __name__ == "__main__":
    main()
