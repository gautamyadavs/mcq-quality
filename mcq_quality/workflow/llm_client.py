"""
llm_client.py — Minimal LLM interface for the agents.

Designed for pedagogical clarity, not flexibility. Students should be able to
read this file and understand exactly what's being sent to the LLM.

Supports OpenAI and Anthropic. Add your own provider in <30 lines if needed.
"""

import json
import os
from typing import Optional


class LLMClient:
    """Thin wrapper over a chat completion API.

    Reads OPENAI_API_KEY or ANTHROPIC_API_KEY from the environment, preferring
    OpenAI when both are set (matching the OpenAI-first ordering used across
    all three repos in this trilogy).

    Optionally reads OPENAI_BASE_URL to support OpenAI-compatible endpoints
    (e.g., Gemini's OpenAI-compatible API at generativelanguage.googleapis.com).
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.provider = provider or self._detect_provider()
        self.model = model or self._default_model()
        self._client = None  # lazy-init

    @staticmethod
    def _detect_provider() -> str:
        # OpenAI is preferred when both keys are present, to match the
        # documented OpenAI-first ordering across all three repos. Override
        # by passing provider="anthropic" explicitly.
        if os.environ.get("OPENAI_API_KEY"):
            return "openai"
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic"
        raise RuntimeError(
            "No LLM API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in your environment."
        )

    def _default_model(self) -> str:
        # Allow overriding the default via environment variables — useful when
        # the README documents this without requiring code changes.
        if self.provider == "anthropic":
            return os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        return os.environ.get("OPENAI_MODEL", "gpt-4o")

    def _ensure_client(self):
        if self._client is not None:
            return
        if self.provider == "anthropic":
            try:
                import anthropic
            except ImportError:
                raise RuntimeError(
                    "anthropic package not installed. Run: "
                    'pip install -e ".[anthropic]" (from the repo directory) '
                    "or pip install anthropic"
                )
            self._client = anthropic.Anthropic()
        else:
            try:
                import openai
            except ImportError:
                raise RuntimeError(
                    "openai package not installed. Run: "
                    'pip install -e ".[openai]" (from the repo directory) '
                    "or pip install openai"
                )
            # Honor OPENAI_BASE_URL so users can point at OpenAI-compatible
            # endpoints (e.g., Gemini's OpenAI-compatible API). The openai
            # SDK does NOT read this env var by default.
            kwargs = {}
            base_url = os.environ.get("OPENAI_BASE_URL")
            if base_url:
                kwargs["base_url"] = base_url
            self._client = openai.OpenAI(**kwargs)

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ) -> str:
        """Single-turn completion. Returns the model's text response."""
        self._ensure_client()
        if self.provider == "anthropic":
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text
        else:
            response = self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return response.choices[0].message.content

    def complete_json(self, system: str, user: str, **kwargs) -> dict:
        """Like complete(), but expects the response to be JSON.

        Returns the parsed JSON or raises ValueError with the raw response
        for debugging. Strips common Markdown code fences.
        """
        text = self.complete(system, user, **kwargs)
        cleaned = text.strip()
        if cleaned.startswith("```"):
            # remove ```json ... ``` fences
            cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Expected JSON response, got:\n{text}\n\nParse error: {e}"
            )
