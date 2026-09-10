"""Subagente 'paper_summarizer': busca en arXiv por la misma palabra clave que
'paper_search' y produce un resumen del abstract del resultado más relevante.

Nota deliberada: el resumen aquí es EXTRACTIVO (primeras oraciones del abstract), no
generado por un LLM -- la capa de abstracción multi-proveedor LLM (Claude/Codex/Gemini)
sigue siendo un punto abierto en PROJECT_BRIEF.md (sección 4, punto 3) y no se resuelve de
paso en este caso de prueba. Cuando esa capa exista, este subagente es el candidato obvio
para conectarla.

Uso: SUBAGENT_ID=<uuid> python -m meridian.subagents.paper_summarizer.main
"""
import os
import sys
from typing import Any

from meridian.subagents import arxiv_client
from meridian.subagents.worker_base import run


def _extractive_summary(abstract: str, max_sentences: int = 2) -> str:
    sentences = [s.strip() for s in abstract.replace("\n", " ").split(". ") if s.strip()]
    return ". ".join(sentences[:max_sentences]).rstrip(".") + "." if sentences else ""


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    query = payload["query"]
    results = arxiv_client.search(query, max_results=1)
    if not results:
        return {"query": query, "top_result": None, "summary": None}

    top = results[0]
    return {
        "query": query,
        "top_result": {"title": top["title"], "url": top["url"]},
        "summary": _extractive_summary(top["abstract"]),
        "summary_method": "extractive (no LLM -- ver docstring de este módulo)",
    }


def main() -> None:
    subagent_id = os.environ.get("SUBAGENT_ID")
    if not subagent_id:
        print("Falta SUBAGENT_ID en el entorno (uuid de subagents.id en Postgres)", file=sys.stderr)
        raise SystemExit(1)
    run(subagent_id, handle)


if __name__ == "__main__":
    main()
