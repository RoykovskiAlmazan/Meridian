"""Adapter para cualquier API compatible con el formato de chat completions de OpenAI --
además de OpenAI mismo, Groq y xAI (Grok) exponen ese mismo formato con solo cambiar la
`base_url`, así que reusan esta clase en vez de duplicar el cliente HTTP.
"""
from __future__ import annotations

import openai

from meridian.llm.base import LLMProvider, LLMResponse


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, *, provider_name: str, base_url: str | None = None):
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._provider_name = provider_name

    def complete(self, *, system: str | None, prompt: str, max_tokens: int = 512) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=messages,
        )
        text = resp.choices[0].message.content or ""
        usage = resp.usage
        return LLMResponse(
            text=text,
            provider=self._provider_name,
            model=self._model,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )


class OpenAIProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model, provider_name="openai")


class GroqProvider(OpenAICompatibleProvider):
    """Groq expone un endpoint compatible con OpenAI en api.groq.com -- mismo cliente
    `openai`, solo cambia base_url. No requiere el SDK propio de Groq."""

    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model, provider_name="groq", base_url="https://api.groq.com/openai/v1")


class XAIProvider(OpenAICompatibleProvider):
    """xAI (Grok) expone el mismo formato compatible con OpenAI en api.x.ai."""

    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model, provider_name="xai", base_url="https://api.x.ai/v1")
