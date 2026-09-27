from __future__ import annotations

import os

from .providers import GeminiProvider, ModelProvider, OllamaProvider, OpenAICompatibleProvider


def create_provider(
    name: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> ModelProvider:
    if name == "gemini":
        return GeminiProvider(model or os.getenv("ADEV_MODEL", "gemini-3.7-flash"), api_key)
    if name == "ollama":
        return OllamaProvider(
            model or os.getenv("ADEV_MODEL", "qwen2.5-coder:7b"),
            base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        )
    if name == "openai-compatible":
        endpoint = base_url or os.getenv("OPENAI_COMPATIBLE_BASE_URL")
        selected_model = model or os.getenv("ADEV_MODEL")
        if not endpoint or not selected_model:
            raise ValueError("openai-compatible requires --base-url and --model")
        return OpenAICompatibleProvider(
            endpoint, selected_model, api_key or os.getenv("OPENAI_COMPATIBLE_API_KEY")
        )
    raise ValueError(f"unknown provider: {name}")
