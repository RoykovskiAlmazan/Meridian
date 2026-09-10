from __future__ import annotations

from google import genai

from meridian.llm.base import LLMProvider, LLMResponse


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def complete(self, *, system: str | None, prompt: str, max_tokens: int = 512) -> LLMResponse:
        config = {"max_output_tokens": max_tokens}
        if system:
            config["system_instruction"] = system

        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        usage = getattr(response, "usage_metadata", None)
        return LLMResponse(
            text=response.text or "",
            provider="gemini",
            model=self._model,
            input_tokens=getattr(usage, "prompt_token_count", None) if usage else None,
            output_tokens=getattr(usage, "candidates_token_count", None) if usage else None,
        )
