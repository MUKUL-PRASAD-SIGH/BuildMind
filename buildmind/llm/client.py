"""
Unified async LLM client for BuildMind.

Routes model calls through the IDE's model infrastructure (Antigravity).
No API keys required for IDE-integrated usage.

For standalone/testing mode, falls back to direct Anthropic/OpenAI SDK calls
if ANTHROPIC_API_KEY or OPENAI_API_KEY are set in the environment.

Architecture Note (Inverted MCP Orchestration):
  When running as an MCP server tool, ACTIVE_MCP_SESSION is set to the FastMCP
  Context session. All LLMClient.complete_sync() calls then route through
  anyio.from_thread.run(_complete_mcp) which fires sampling/createMessage back
  to the IDE — using the IDE's LLM connection without any API keys.
"""
from __future__ import annotations

import asyncio
import contextvars
import json
import os
from typing import AsyncIterator, Optional, Any

from buildmind.config.settings import BuildMindConfig

# ── MCP Session context var (thread-safe, per-task isolation) ────────────────

# Use a ContextVar instead of a plain global so concurrent tool calls
# from different async tasks don't corrupt each other's sessions.
_mcp_session_var: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "mcp_session", default=None
)

# Backward-compatible shim: write to this and it sets the ContextVar
class _SessionProxy:
    def __set_name__(self, owner, name):
        self._name = name
    def __get__(self, obj, objtype=None):
        return _mcp_session_var.get()
    def __set__(self, obj, value):
        _mcp_session_var.set(value)

# Module-level attribute used by mcp_server.py: llm_client.ACTIVE_MCP_SESSION = ctx.session
ACTIVE_MCP_SESSION: Any = None

def set_mcp_session(session: Any) -> contextvars.Token:
    """Set the MCP session for the current async context. Returns token for reset."""
    return _mcp_session_var.set(session)

def get_mcp_session() -> Any:
    """Get the active MCP session, or None if running standalone."""
    # Also check the plain global for backward compat
    global ACTIVE_MCP_SESSION
    return _mcp_session_var.get() or ACTIVE_MCP_SESSION


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
    1. MCP session active  -> sampling/createMessage to IDE (no API key!)
    2. ANTHROPIC_API_KEY   -> direct Anthropic SDK
    3. OPENAI_API_KEY      -> direct OpenAI SDK
    4. None of the above   -> raises helpful EnvironmentError
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
        Automatically routes to MCP sampling if an IDE session is active.
        """
        session = get_mcp_session()
        provider, model_id = resolve_model(model)

        if session is not None:
            return await self._complete_mcp(
                session, system_prompt, user_prompt, model_id,
                max_tokens, temperature, json_mode
            )

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
        """
        Synchronous wrapper. Works correctly in both modes:
        - MCP worker thread: uses anyio.from_thread.run() to post to event loop
        - Standalone CLI: uses asyncio.run() to create new event loop
        """
        session = get_mcp_session()

        if session is not None:
            # FastMCP runs sync tools in AnyIO worker threads.
            # We MUST use anyio.from_thread.run() to dispatch back to the
            # running event loop — calling asyncio.run() here would deadlock.
            # However if we're not inside an AnyIO worker (e.g. unit test), fall back.
            try:
                import anyio.from_thread
                provider, model_id = resolve_model(model)
                return anyio.from_thread.run(
                    self._complete_mcp,
                    session, system_prompt, user_prompt, model_id,
                    max_tokens, temperature, json_mode
                )
            except Exception as anyio_err:
                # Not inside an AnyIO worker thread — create a fresh event loop
                # This happens in test environments or direct Python invocations
                if "AnyIO" in str(anyio_err) or "event loop" in str(anyio_err).lower() or "NoEventLoop" in type(anyio_err).__name__:
                    provider, model_id = resolve_model(model)
                    return asyncio.run(self._complete_mcp(
                        session, system_prompt, user_prompt, model_id,
                        max_tokens, temperature, json_mode
                    ))
                raise  # Some other error — propagate

        # Standalone CLI mode: create a fresh event loop
        return asyncio.run(self.complete(
            system_prompt, user_prompt, model,
            max_tokens, temperature, json_mode
        ))

    # ── MCP Sampling (Agentic Proxy) ──────────────────────────────────────────

    async def _complete_mcp(
        self,
        session: Any,
        system_prompt: str,
        user_prompt: str,
        model_id: str,
        max_tokens: int,
        temperature: float,
        json_mode: bool,
    ) -> str:
        """
        Fire a sampling/createMessage request to the IDE.
        The IDE proxies this to its active LLM (Claude, Gemini, etc.)
        and returns the completion — no API key needed server-side.
        """
        from mcp.types import SamplingMessage, TextContent

        # Merge system prompt into the user message since MCP sampling
        # doesn't always have a separate system channel on all clients.
        prompt = f"{user_prompt}"
        if json_mode:
            prompt += "\n\nRespond ONLY with valid JSON. No markdown, no explanation."

        result = await session.create_message(
            messages=[
                SamplingMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt),
                )
            ],
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            # No explicit model hints: let IDE use whatever model user has selected.
            # This is intentional — the IDE knows best which model is available.
        )

        # result.content is TextContent with a .text attribute
        if hasattr(result.content, "text"):
            return result.content.text
        return str(result.content)

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

        if json_mode:
            user_prompt = user_prompt + "\n\nRespond ONLY with valid JSON. No markdown, no explanation."

        message = await client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
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
