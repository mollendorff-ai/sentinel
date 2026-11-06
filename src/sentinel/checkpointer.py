"""Checkpointer factory — SQLite persistence for pipeline state."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(".sentinel/checkpoints.db")


def create_checkpointer(
    db_path: Path = DEFAULT_DB_PATH,
) -> AbstractAsyncContextManager[AsyncSqliteSaver]:
    """Create an async SQLite checkpointer for pipeline persistence.

    Parameters
    ----------
    db_path
        Path to the SQLite database file. Parent directories are created
        automatically if they don't exist.

    Returns
    -------
    AbstractAsyncContextManager[AsyncSqliteSaver]
        An async context manager (use ``async with``); the pipeline is async, so
        the synchronous ``SqliteSaver`` cannot be used.

    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Checkpointer: SQLite at %s", db_path)
    return AsyncSqliteSaver.from_conn_string(str(db_path))
