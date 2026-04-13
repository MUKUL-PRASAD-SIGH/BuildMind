"""
Unified async LLM client for BuildMind.

Routes model calls through the IDE's model infrastructure (Antigravity).
No API keys required for IDE-integrated usage.

For standalone/testing mode, falls back to direct Anthropic/OpenAI SDK calls
if ANTHROPIC_API_KEY or OPENAI_API_KEY are set in the environment.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import AsyncIterator, Optional

from buildmind.config.settings import BuildMindConfig

# ── Provider detection ────────────────────────────────────────────────────────

def _has_anthropic_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

def _has_openai_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


# ── Model name normalization ──────────────────────────────────────────────────

# Map friendly names -> actual API model IDs
MODEL_ALIASES: dict[str, dict[str, str]] = {
    "claude-opus":   {
        "anthropic": "claude-opus-4-5",
        "display":   "claude-opus-4-5",
    },
    "claude-sonnet": {
        "anthropic": "claude-sonnet-4-5",
        "display":   "claude-sonnet-4-5",
    },
    "claude-haiku":  {
        "anthropic": "claude-haiku-3-5",
        "display":   "claude-haiku-3-5",
    },
    "gemini-pro":    {
        "openai":   "gemini-pro",       # via OpenAI-compat endpoint
        "display":  "gemini-pro",
    },
    "gemini-flash":  {
        "openai":   "gemini-flash",
        "display":  "gemini-flash",
    },
    "gpt-4o":        {
        "openai":   "gpt-4o",
        "display":  "gpt-4o",
    },
    "gpt-4o-mini":   {
        "openai":   "gpt-4o-mini",
        "display":  "gpt-4o-mini",
    },
}

def resolve_model(name: str) -> tuple[str, str]:
    """Returns (provider, api_model_id) for a friendly model name."""
    alias = MODEL_ALIASES.get(name)
    if alias:
        if "anthropic" in alias and _has_anthropic_key():
            return ("anthropic", alias["anthropic"])
        if "openai" in alias and _has_openai_key():
            return ("openai", alias["openai"])
        # Default: try anthropic first
        if "anthropic" in alias:
            return ("anthropic", alias["anthropic"])
        if "openai" in alias:
            return ("openai", alias["openai"])
    # Fall through: treat as literal model ID, guess provider
    if name.startswith("claude"):
        return ("anthropic", name)
    return ("openai", name)


# ── Main LLM client ───────────────────────────────────────────────────────────

class LLMClient:
    """
    Unified LLM client for BuildMind.

    Priority:
    1. ANTHROPIC_API_KEY set  -> direct Anthropic SDK (SDK call)
    2. OPENAI_API_KEY set     -> direct OpenAI SDK (SDK call)
    3. Neither set            -> raises helpful error with setup instructions
    """

    def __init__(self, config: BuildMindConfig):
        self.config = config

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "claude-sonnet",
        max_tokens: int = 4096,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        """
        Send a completion request and return the full text response.
        Blocking (wraps async in sync for CLI use).
        """
        provider, model_id = resolve_model(model)

        if provider == "anthropic":
            return await self._complete_anthropic(
                system_prompt, user_prompt, model_id,
                max_tokens, temperature, json_mode
            )
        elif provider == "openai":
            return await self._complete_openai(
                system_prompt, user_prompt, model_id,
                max_tokens, temperature, json_mode
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def complete_sync(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "claude-sonnet",
        max_tokens: int = 4096,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        """Synchronous wrapper for CLI use."""
        return asyncio.run(self.complete(
            system_prompt, user_prompt, model,
            max_tokens, temperature, json_mode
        ))

    # ── Anthropic ─────────────────────────────────────────────────────────────

    async def _complete_anthropic(
        self,
        system_prompt: str,
        user_prompt: str,
        model_id: str,
        max_tokens: int,
        temperature: float,
        json_mode: bool,
    ) -> str:
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

        if not _has_anthropic_key():
            raise EnvironmentError(
                "ANTHROPIC_API_KEY not set.\n"
                "Set it in your environment or .env file:\n"
                "  ANTHROPIC_API_KEY=sk-ant-...\n"
                "Or use BuildMind via Antigravity (no key needed) — see docs/15-ide-integration.md"
            )

        client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        extra = {}
        if json_mode:
            user_prompt = user_prompt + "\n\nRespond ONLY with valid JSON. No markdown, no explanation."

        message = await client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            **extra,
        )
        return message.content[0].text

    # ── OpenAI ────────────────────────────────────────────────────────────────

    async def _complete_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        model_id: str,
        max_tokens: int,
        temperature: float,
        json_mode: bool,
    ) -> str:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

        if not _has_openai_key():
            raise EnvironmentError(
                "OPENAI_API_KEY not set.\n"
                "Set it in your environment or .env file:\n"
                "  OPENAI_API_KEY=sk-...\n"
            )

        client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

        kwargs: dict = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await client.chat.completions.create(
            model=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            **kwargs,
        )
        return response.choices[0].message.content

    # ── Retry wrapper ─────────────────────────────────────────────────────────

    async def complete_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "claude-sonnet",
        max_tokens: int = 4096,
        temperature: float = 0.2,
        json_mode: bool = False,
        max_attempts: int = 3,
    ) -> str:
        """
        Retry with model escalation on failure.
        Haiku -> Sonnet -> Opus
        """
        escalation = {
            "claude-haiku":  "claude-sonnet",
            "claude-sonnet": "claude-opus",
            "claude-opus":   "claude-opus",   # final
        }

        last_err: Optional[Exception] = None
        current_model = model

        for attempt in range(1, max_attempts + 1):
            try:
                return await self.complete(
                    system_prompt, user_prompt, current_model,
                    max_tokens, temperature, json_mode
                )
            except Exception as e:
                last_err = e
                next_model = escalation.get(current_model, current_model)
                if next_model == current_model or attempt == max_attempts:
                    break
                current_model = next_model

        raise RuntimeError(
            f"LLM call failed after {max_attempts} attempts. Last error: {last_err}"
        )
