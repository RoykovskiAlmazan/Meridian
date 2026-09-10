"""Subagente 'paper_search': busca en arXiv por palabra clave y devuelve los papers
más relevantes. Caso de prueba de dominio real (investigación) para Meridian -- ver
docs/design/0007-paper-search-app.md.

Uso: SUBAGENT_ID=<uuid> python -m meridian.subagents.paper_search.main
"""
import os
import sys
from typing import Any

from meridian.subagents import arxiv_client
from meridian.subagents.worker_base import run


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    query = payload["query"]
    max_results = payload.get("max_results", 5)
    results = arxiv_client.search(query, max_results=max_results)
    return {
        "query": query,
        "count": len(results),
        "results": [{"title": r["title"], "url": r["url"], "published": r["published"], "authors": r["authors"]} for r in results],
    }


def main() -> None:
    subagent_id = os.environ.get("SUBAGENT_ID")
    if not subagent_id:
        print("Falta SUBAGENT_ID en el entorno (uuid de subagents.id en Postgres)", file=sys.stderr)
        raise SystemExit(1)
    run(subagent_id, handle)


if __name__ == "__main__":
    main()
