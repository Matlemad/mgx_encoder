"""LLM provider abstraction for AI-powered modules (e.g. the Draft Composer).

Real providers (OpenAI) are selected via environment variables, with a safe
fallback to a heuristic mock so the app always runs offline:

- LLM_PROVIDER=openai + OPENAI_API_KEY present  → OpenAILLMProvider
- otherwise                                      → MockLLMProvider

No provider ever reproduces copyrighted text; copyright safety is enforced by
the calling layer (system prompts + post-processing).
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod

try:  # dotenv is optional but used everywhere else in the app
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


class LLMProvider(ABC):
    name: str = "base"
    is_live: bool = False

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 800,
        temperature: float = 0.8,
    ) -> str:
        ...


class MockLLMProvider(LLMProvider):
    """Returns a marker string; real generation is handled heuristically upstream."""

    name = "mock"
    is_live = False

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 800,
        temperature: float = 0.8,
    ) -> str:
        return f"[Mock LLM] No live LLM configured ({len(prompt)} chars of context received)."


class OpenAILLMProvider(LLMProvider):
    """OpenAI Chat Completions provider (SDK >= 1.0)."""

    name = "openai"
    is_live = True

    def __init__(self, api_key: str, model: str | None = None) -> None:
        from openai import OpenAI  # imported lazily so the dep stays optional

        self._client = OpenAI(api_key=api_key)
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 800,
        temperature: float = 0.8,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return (resp.choices[0].message.content or "").strip()


def get_llm_provider() -> LLMProvider:
    """Factory: real OpenAI provider when configured, else heuristic mock."""
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if provider in ("", "openai") and key:
        try:
            return OpenAILLMProvider(api_key=key)
        except Exception:  # noqa: BLE001 - never break the app on init/import
            pass
    return MockLLMProvider()


def llm_status() -> dict[str, str]:
    """Lightweight status for UI banners (no network calls)."""
    provider = os.environ.get("LLM_PROVIDER", "openai").strip().lower() or "openai"
    has_key = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    try:
        import openai  # noqa: F401
        sdk = True
    except Exception:  # noqa: BLE001
        sdk = False
    live = provider == "openai" and has_key and sdk
    reason = ""
    if not live:
        if not has_key:
            reason = "missing OPENAI_API_KEY"
        elif not sdk:
            reason = "openai package not installed (pip install openai)"
        elif provider != "openai":
            reason = f"LLM_PROVIDER={provider} not supported"
    return {
        "provider": provider,
        "status": "live" if live else "mock",
        "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "reason": reason,
    }
