"""Interfaz mínima que cualquier proveedor de LLM debe implementar -- ver
docs/design/0009-llm-provider-layer.md. Deliberadamente pequeña (un solo método,
completions de una sola vuelta) porque el único consumidor real hoy (`paper_summarizer`)
solo necesita eso; tool-calling/streaming se agregan cuando un subagente real los necesite,
no antes (no se diseña para un futuro hipotético).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, *, system: str | None, prompt: str, max_tokens: int = 512) -> LLMResponse:
        """Una sola vuelta de completion. Sin tool-calling ni streaming todavía."""
