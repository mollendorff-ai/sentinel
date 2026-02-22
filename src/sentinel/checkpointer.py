"""Checkpointer factory — SQLite persistence for pipeline state."""

from __future__ import annotations

import logging
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(".sentinel/checkpoints.db")


def create_checkpointer(db_path: Path = DEFAULT_DB_PATH) -> SqliteSaver:
    """Create a SQLite checkpointer for pipeline persistence.

    Parameters
    ----------
    db_path
        Path to the SQLite database file. Parent directories are created
        automatically if they don't exist.

    Returns
    -------
    SqliteSaver
        A context-manager checkpointer backed by SQLite.

    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Checkpointer: SQLite at %s", db_path)
    return SqliteSaver.from_conn_string(str(db_path))
