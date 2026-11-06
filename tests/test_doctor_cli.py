"""Tests for the `aegis doctor` CLI command (Phase O-1)."""

from __future__ import annotations

import os


def test_doctor_flag_off(capsys):
    """When the DOCTOR flag is disabled, the command prints a hint and returns."""
    os.environ.pop("OWNERAI_FEATURE_DOCTOR", None)
    from ownerai.features import is_enabled
    assert is_enabled("DOCTOR") is False

    from main import cmd_doctor

    cmd_doctor()
    captured = capsys.readouterr()
    assert "DOCTOR feature is not enabled" in captured.out


def test_doctor_flag_on(capsys):
    """When the DOCTOR flag is enabled, the command prints a health report."""
    os.environ["OWNERAI_FEATURE_DOCTOR"] = "1"
    try:
        from ownerai.features import is_enabled
        assert is_enabled("DOCTOR") is True

        from main import cmd_doctor

        cmd_doctor()
        captured = capsys.readouterr()
        assert "Aegis AI Doctor Report" in captured.out
        assert "Overall:" in captured.out
        assert "database" in captured.out.lower()
        assert "disk" in captured.out.lower()
        assert "model" in captured.out.lower()
    finally:
        os.environ.pop("OWNERAI_FEATURE_DOCTOR", None)
