"""LLM provider abstraction for AI-powered palette modules."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 300) -> str: ...


class MockLLMProvider(LLMProvider):
    """Returns heuristic-generated text, no real LLM calls."""

    def generate(self, prompt: str, max_tokens: int = 300) -> str:
        return f"[Mock LLM] Prompt received ({len(prompt)} chars). Real provider not configured."


def get_llm_provider() -> LLMProvider:
    """Factory: returns mock for now, future OpenAI/Claude via env."""
    return MockLLMProvider()
