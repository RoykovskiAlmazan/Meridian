"""Cliente mínimo del API público de arXiv, compartido por los subagentes de ejemplo
`paper_search` y `paper_summarizer` -- ambos son un caso de prueba concreto para demostrar
que Meridian orquesta dominios reales (aquí: investigación), no solo el eco del entregable 2.
No hay nada arXiv-específico en la plataforma; esto vive enteramente en estos subagentes.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import requests

_ARXIV_API = "http://export.arxiv.org/api/query"
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Busca en arXiv y devuelve una lista de papers (más relevante primero)."""
    resp = requests.get(
        _ARXIV_API,
        params={
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        },
        timeout=15,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.text)

    results = []
    for entry in root.findall("atom:entry", _ATOM_NS):
        title = entry.findtext("atom:title", default="", namespaces=_ATOM_NS).strip()
        arxiv_url = entry.findtext("atom:id", default="", namespaces=_ATOM_NS).strip()
        published = entry.findtext("atom:published", default="", namespaces=_ATOM_NS).strip()
        summary = entry.findtext("atom:summary", default="", namespaces=_ATOM_NS).strip()
        authors = [
            author.findtext("atom:name", default="", namespaces=_ATOM_NS).strip()
            for author in entry.findall("atom:author", _ATOM_NS)
        ]
        results.append({
            "title": title,
            "url": arxiv_url,
            "published": published,
            "authors": authors,
            "abstract": summary,
        })
    return results
