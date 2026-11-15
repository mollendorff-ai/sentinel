"""Tests for the LLM factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sentinel.handoff import HandoffLLM
from sentinel.llm import API_KEY_VARIABLES, DEFAULT_MAX_TOKENS, get_llm, missing_api_key

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
        model="claude-sonnet-5-5",
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
        model="claude-sonnet-5-5",
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


def test_chat_provider_needs_no_package_or_key() -> None:
    """SENTINEL_LLM_PROVIDER=chat returns the hand-off stand-in for the agent's role."""
    with (
        patch.dict("os.environ", {"SENTINEL_LLM_PROVIDER": "chat"}, clear=True),
        patch("sentinel.llm.importlib") as mock_importlib,
    ):
        llm = get_llm(role="modeler")

    assert isinstance(llm, HandoffLLM)
    assert llm.role == "modeler"
    mock_importlib.import_module.assert_not_called()


def test_unknown_provider_lists_chat() -> None:
    """The error for an unknown provider names chat among the choices."""
    with (
        patch.dict("os.environ", {"SENTINEL_LLM_PROVIDER": "foo"}, clear=True),
        pytest.raises(ValueError, match="chat"),
    ):
        get_llm()


@pytest.mark.parametrize(
    ("provider", "value", "expected"),
    [
        ("chat", "", ""),
        ("nobody", "", ""),
        ("anthropic", "sk-real", ""),
        ("anthropic", "", "ANTHROPIC_API_KEY is not set"),
        ("openai", "your-openai-api-key", "OPENAI_API_KEY still holds the example's placeholder"),
    ],
)
def test_missing_api_key(
    monkeypatch: pytest.MonkeyPatch, provider: str, value: str, expected: str
) -> None:
    """A provider that needs a key is reported when the key is unset or the placeholder."""
    for variable in API_KEY_VARIABLES.values():
        monkeypatch.delenv(variable, raising=False)
    if value:
        monkeypatch.setenv(API_KEY_VARIABLES[provider], value)
    problem = missing_api_key(provider)
    if expected:
        assert expected in problem
        assert "SENTINEL_LLM_PROVIDER=chat" in problem
    else:
        assert problem == ""
