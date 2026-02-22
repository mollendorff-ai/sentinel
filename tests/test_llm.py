"""Tests for the LLM factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sentinel.llm import DEFAULT_MAX_TOKENS, get_llm

CUSTOM_MAX_TOKENS = 4096


def _mock_module(class_name: str = "ChatFake") -> MagicMock:
    """Build a fake module with a chat model class."""
    mock_cls = MagicMock()
    mod = MagicMock()
    setattr(mod, class_name, mock_cls)
    return mod


def test_default_provider_is_anthropic() -> None:
    """No env vars -> uses ChatAnthropic with default model."""
    mod = _mock_module("ChatAnthropic")
    with (
        patch.dict("os.environ", {}, clear=True),
        patch("sentinel.llm.importlib") as mock_importlib,
    ):
        mock_importlib.import_module.return_value = mod
        get_llm()

    mod.ChatAnthropic.assert_called_once_with(
        model="claude-opus-4-6",
        temperature=0,
        max_tokens=DEFAULT_MAX_TOKENS,
    )


def test_google_provider() -> None:
    """SENTINEL_LLM_PROVIDER=google -> ChatGoogleGenerativeAI."""
    mod = _mock_module("ChatGoogleGenerativeAI")
    with (
        patch.dict("os.environ", {"SENTINEL_LLM_PROVIDER": "google"}, clear=True),
        patch("sentinel.llm.importlib") as mock_importlib,
    ):
        mock_importlib.import_module.return_value = mod
        get_llm()

    mod.ChatGoogleGenerativeAI.assert_called_once_with(
        model="gemini-2.5-flash",
        temperature=0,
        max_output_tokens=DEFAULT_MAX_TOKENS,
    )


def test_openai_provider() -> None:
    """SENTINEL_LLM_PROVIDER=openai -> ChatOpenAI."""
    mod = _mock_module("ChatOpenAI")
    with (
        patch.dict("os.environ", {"SENTINEL_LLM_PROVIDER": "openai"}, clear=True),
        patch("sentinel.llm.importlib") as mock_importlib,
    ):
        mock_importlib.import_module.return_value = mod
        get_llm()

    mod.ChatOpenAI.assert_called_once_with(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=DEFAULT_MAX_TOKENS,
    )


def test_groq_provider() -> None:
    """SENTINEL_LLM_PROVIDER=groq -> ChatGroq."""
    mod = _mock_module("ChatGroq")
    with (
        patch.dict("os.environ", {"SENTINEL_LLM_PROVIDER": "groq"}, clear=True),
        patch("sentinel.llm.importlib") as mock_importlib,
    ):
        mock_importlib.import_module.return_value = mod
        get_llm()

    mod.ChatGroq.assert_called_once_with(
        model="llama-3.3-70b-versatile",
        temperature=0,
        max_tokens=DEFAULT_MAX_TOKENS,
    )


def test_custom_model_override() -> None:
    """SENTINEL_LLM_MODEL overrides the default model for the provider."""
    mod = _mock_module("ChatAnthropic")
    env = {"SENTINEL_LLM_PROVIDER": "anthropic", "SENTINEL_LLM_MODEL": "claude-haiku-4-5-20251001"}
    with (
        patch.dict("os.environ", env, clear=True),
        patch("sentinel.llm.importlib") as mock_importlib,
    ):
        mock_importlib.import_module.return_value = mod
        get_llm()

    mod.ChatAnthropic.assert_called_once_with(
        model="claude-haiku-4-5-20251001",
        temperature=0,
        max_tokens=DEFAULT_MAX_TOKENS,
    )


def test_max_tokens_passthrough() -> None:
    """max_tokens kwarg is forwarded to the provider constructor."""
    mod = _mock_module("ChatAnthropic")
    with (
        patch.dict("os.environ", {}, clear=True),
        patch("sentinel.llm.importlib") as mock_importlib,
    ):
        mock_importlib.import_module.return_value = mod
        get_llm(max_tokens=CUSTOM_MAX_TOKENS)

    mod.ChatAnthropic.assert_called_once_with(
        model="claude-opus-4-6",
        temperature=0,
        max_tokens=CUSTOM_MAX_TOKENS,
    )


def test_unknown_provider_raises() -> None:
    """Unknown provider raises ValueError with helpful message."""
    with (
        patch.dict("os.environ", {"SENTINEL_LLM_PROVIDER": "foo"}, clear=True),
        pytest.raises(ValueError, match="Unknown LLM provider: 'foo'"),
    ):
        get_llm()


def test_missing_package_raises() -> None:
    """Missing provider package raises ImportError with install hint."""
    with (
        patch.dict("os.environ", {"SENTINEL_LLM_PROVIDER": "groq"}, clear=True),
        patch("sentinel.llm.importlib") as mock_importlib,
    ):
        mock_importlib.import_module.side_effect = ImportError("No module named 'langchain_groq'")
        with pytest.raises(ImportError, match="pip install langchain-groq"):
            get_llm()
