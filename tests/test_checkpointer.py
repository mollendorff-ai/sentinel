"""Tests for the SQLite checkpointer factory."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

from sentinel.checkpointer import DEFAULT_DB_PATH, create_checkpointer


def test_create_checkpointer_returns_context_manager(tmp_path: Path) -> None:
    """Verify factory calls SqliteSaver.from_conn_string with the DB path."""
    mock_saver = MagicMock()
    db_path = tmp_path / "test" / "checkpoints.db"

    with patch(
        "sentinel.checkpointer.SqliteSaver",
    ) as mock_cls:
        mock_cls.from_conn_string.return_value = mock_saver
        result = create_checkpointer(db_path=db_path)

    mock_cls.from_conn_string.assert_called_once_with(str(db_path))
    assert result is mock_saver


def test_create_checkpointer_creates_parent_dirs(tmp_path: Path) -> None:
    """Verify factory creates parent directories when they don't exist."""
    db_path = tmp_path / "deep" / "nested" / "checkpoints.db"

    with patch(
        "sentinel.checkpointer.SqliteSaver",
    ) as mock_cls:
        mock_cls.from_conn_string.return_value = MagicMock()
        create_checkpointer(db_path=db_path)

    assert db_path.parent.exists()


def test_create_checkpointer_uses_default_path() -> None:
    """Verify factory uses DEFAULT_DB_PATH when no argument is provided."""
    with patch(
        "sentinel.checkpointer.SqliteSaver",
    ) as mock_cls:
        mock_cls.from_conn_string.return_value = MagicMock()
        create_checkpointer()

    mock_cls.from_conn_string.assert_called_once_with(str(DEFAULT_DB_PATH))
