"""Tests for SecretStore integration."""

from __future__ import annotations

from pathlib import Path

from shipcadence.secrets import delete_token, get_token, save_token


def test_save_and_get_token(tmp_path: Path) -> None:
    save_token("ghp_test_secret_123", db_dir=tmp_path)
    result = get_token(db_dir=tmp_path)
    assert result == "ghp_test_secret_123"


def test_get_token_returns_none_when_empty(tmp_path: Path) -> None:
    result = get_token(db_dir=tmp_path)
    assert result is None


def test_delete_token(tmp_path: Path) -> None:
    save_token("ghp_to_delete", db_dir=tmp_path)
    assert delete_token(db_dir=tmp_path) is True
    assert get_token(db_dir=tmp_path) is None


def test_delete_nonexistent_token(tmp_path: Path) -> None:
    assert delete_token(db_dir=tmp_path) is False


def test_overwrite_token(tmp_path: Path) -> None:
    save_token("ghp_first", db_dir=tmp_path)
    save_token("ghp_second", db_dir=tmp_path)
    assert get_token(db_dir=tmp_path) == "ghp_second"
