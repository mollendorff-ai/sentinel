"""Tests for Sentinel CLI entry point."""

import pytest

from sentinel.__main__ import main


def test_main_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify main() outputs the expected version banner."""
    main()

    out = capsys.readouterr().out
    assert "Sentinel v0.1.0" in out
