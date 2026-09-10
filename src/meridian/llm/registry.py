"""Resuelve qué LLMProvider usar para un subagente dado, a partir de su configuración en
Postgres (`subagent_llm_config`) + la credencial real resuelta en runtime desde Vault.
Ningún subagente ni el `main` deben instanciar un SDK de proveedor directamente -- siempre
pasan por aquí, para poder mezclar proveedores por subagente sin acoplar el resto del
sistema a un SDK concreto (decisión #8 del brief).
"""
from __future__ import annotations

from uuid import UUID

from meridian.identity import repository
from meridian.llm.base import LLMProvider
from meridian.secrets.vault_client import resolve_secret_ref


def _build(provider: str, model: str, api_key: str) -> LLMProvider:
    if provider == "anthropic":
        from meridian.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=api_key, model=model)
    if provider == "openai":
        from meridian.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=api_key, model=model)
    if provider == "groq":
        from meridian.llm.openai_provider import GroqProvider
        return GroqProvider(api_key=api_key, model=model)
    if provider == "xai":
        from meridian.llm.openai_provider import XAIProvider
        return XAIProvider(api_key=api_key, model=model)
    if provider == "gemini":
        from meridian.llm.gemini_provider import GeminiProvider
        return GeminiProvider(api_key=api_key, model=model)
    raise ValueError(f"proveedor LLM no soportado todavía: {provider!r}")


def get_provider_for_subagent(subagent_id: str) -> LLMProvider | None:
    """None si el subagente no tiene un proveedor LLM configurado -- el caller decide
    el fallback (ej. paper_summarizer usa resumen extractivo si esto devuelve None)."""
    config = repository.get_subagent_llm_config(UUID(subagent_id))
    if config is None:
        return None
    api_key = resolve_secret_ref(config["credential_ref"])
    return _build(config["provider"], config["model"], api_key)
