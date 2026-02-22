"""LLM factory -- configurable provider via environment variables."""

from __future__ import annotations

import importlib
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)

PROVIDER_DEFAULTS: dict[str, tuple[str, str]] = {
    "anthropic": ("langchain_anthropic", "claude-sonnet-4-20250514"),
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


DEFAULT_MAX_TOKENS = 2048


def get_llm(*, max_tokens: int = DEFAULT_MAX_TOKENS) -> BaseChatModel:
    """Return a chat model configured via environment variables.

    Parameters
    ----------
    max_tokens
        Maximum tokens for the response.  Defaults to 2048.

    Environment Variables
    ---------------------
    SENTINEL_LLM_PROVIDER
        One of ``anthropic``, ``openai``, ``google``, ``groq``.
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

    if provider not in PROVIDER_DEFAULTS:
        msg = (
            f"Unknown LLM provider: {provider!r}. "
            f"Supported: {', '.join(sorted(PROVIDER_DEFAULTS))}"
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
