"""LLM factory -- configurable provider via environment variables."""

from __future__ import annotations

import importlib
import logging
import os
from typing import TYPE_CHECKING

from sentinel.handoff import CHAT_PROVIDER, HandoffLLM

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)

PROVIDER_DEFAULTS: dict[str, tuple[str, str]] = {
    "anthropic": ("langchain_anthropic", "claude-sonnet-5-5"),
    "openai": ("langchain_openai", "gpt-4o-mini"),
    "google": ("langchain_google_genai", "gemini-2.5-flash"),
    "groq": ("langchain_groq", "llama-3.3-70b-versatile"),
}
"""Map of provider name to (package_module, default_model)."""

_CLASS_NAMES: dict[str, str] = {
    "anthropic": "ChatAnthropic",
    "openai": "ChatOpenAI",
    "google": "ChatGoogleGenerativeAI",
    "groq": "ChatGroq",
}


API_KEY_VARIABLES: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
}
"""The environment variable that holds each provider's API key."""

_PLACEHOLDER_PREFIX = "your-"
"""How ``.env.example`` writes a key that was never filled in."""

DEFAULT_MAX_TOKENS = 2048


def missing_api_key(provider: str) -> str:
    """Return why *provider* cannot be called (no key, or the example's placeholder), or ``""``.

    The ``chat`` provider needs no key, and an unknown provider is reported by
    :func:`get_llm`.
    """
    variable = API_KEY_VARIABLES.get(provider)
    if variable is None:
        return ""
    value = os.environ.get(variable, "").strip()
    if value and not value.startswith(_PLACEHOLDER_PREFIX):
        return ""
    state = "still holds the example's placeholder" if value else "is not set"
    return (
        f"SENTINEL_LLM_PROVIDER={provider} needs an API key, and {variable} {state}.\n"
        f"Set {variable} in .env, or run in a chat with SENTINEL_LLM_PROVIDER=chat "
        "(no key needed; see the README)."
    )


def get_llm(*, max_tokens: int = DEFAULT_MAX_TOKENS, role: str = "llm") -> BaseChatModel:
    """Return a chat model configured via environment variables.

    Parameters
    ----------
    max_tokens
        Maximum tokens for the response.  Defaults to 2048.
    role
        The agent asking (``research``, ``modeler``, ``synthesizer``).  Used by the
        ``chat`` provider to name the prompt files.

    Environment Variables
    ---------------------
    SENTINEL_LLM_PROVIDER
        One of ``anthropic``, ``openai``, ``google``, ``groq``, or ``chat``: no API,
        the AI in a chat answers each prompt through files (ADR-013).
        Defaults to ``anthropic``.
    SENTINEL_LLM_MODEL
        Optional model name override.  When unset, uses the default
        model for the chosen provider.

    Returns
    -------
    BaseChatModel
        A LangChain chat model ready for ``.ainvoke()`` calls.

    Raises
    ------
    ValueError
        If the provider name is not recognised.
    ImportError
        If the required LangChain provider package is not installed.

    """
    provider = os.environ.get("SENTINEL_LLM_PROVIDER", "anthropic").lower()

    if provider == CHAT_PROVIDER:
        logger.info("LLM: answered in the chat (%s)", role)
        return HandoffLLM(role)  # type: ignore[return-value]

    if provider not in PROVIDER_DEFAULTS:
        msg = (
            f"Unknown LLM provider: {provider!r}. "
            f"Supported: {', '.join(sorted([*PROVIDER_DEFAULTS, CHAT_PROVIDER]))}"
        )
        raise ValueError(msg)

    package, default_model = PROVIDER_DEFAULTS[provider]
    model = os.environ.get("SENTINEL_LLM_MODEL", default_model)
    class_name = _CLASS_NAMES[provider]

    try:
        mod = importlib.import_module(package)
    except ImportError as exc:
        msg = (
            f"Provider {provider!r} requires package {package.replace('_', '-')}. "
            f"Install it with: pip install {package.replace('_', '-')}"
        )
        raise ImportError(msg) from exc

    cls = getattr(mod, class_name)
    logger.info("LLM: %s/%s (via %s)", provider, model, class_name)

    # Google uses max_output_tokens; all others use max_tokens.
    token_kwarg = "max_output_tokens" if provider == "google" else "max_tokens"
    return cls(model=model, temperature=0, **{token_kwarg: max_tokens})  # type: ignore[no-any-return]
