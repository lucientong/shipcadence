"""Secret management for ShipCadence using Dagloom's SecretStore.

Provides a thin wrapper that manages the Dagloom ``Database`` and
``Encryptor`` lifecycle so callers don't need to deal with async
setup/teardown directly.

As of Dagloom v1.0.2, ``Encryptor`` natively supports ``key_file``
for auto-generating and persisting the master key — no manual
workaround needed.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from dagloom.security.encryption import Encryptor
from dagloom.security.secrets import SecretStore
from dagloom.store.db import Database

_DEFAULT_DB_DIR = Path.home() / ".shipcadence"
_DB_NAME = "shipcadence.db"
_KEY_FILE = "master.key"

GITHUB_TOKEN_KEY = "GITHUB_TOKEN"


async def _open_store(db_dir: Path | None = None) -> tuple[Database, SecretStore]:
    """Create and connect a Database + SecretStore pair.

    Returns (db, store) — caller must ``await db.close()`` when done.
    """
    base = db_dir or _DEFAULT_DB_DIR
    base.mkdir(parents=True, exist_ok=True)

    db = Database(db_path=base / _DB_NAME)
    await db.connect()

    encryptor = Encryptor(key_file=base / _KEY_FILE)
    store = SecretStore(db=db, encryptor=encryptor)
    return db, store


async def _save_token(token: str, db_dir: Path | None = None) -> None:
    db, store = await _open_store(db_dir)
    try:
        await store.set(GITHUB_TOKEN_KEY, token)
    finally:
        await db.close()


async def _get_token(db_dir: Path | None = None) -> str | None:
    db, store = await _open_store(db_dir)
    try:
        return await store.get(GITHUB_TOKEN_KEY)
    finally:
        await db.close()


async def _delete_token(db_dir: Path | None = None) -> bool:
    db, store = await _open_store(db_dir)
    try:
        return await store.delete(GITHUB_TOKEN_KEY)
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Synchronous public API (for use in Click commands)
# ---------------------------------------------------------------------------


def save_token(token: str, db_dir: Path | None = None) -> None:
    """Encrypt and store the GitHub token."""
    asyncio.run(_save_token(token, db_dir))


def get_token(db_dir: Path | None = None) -> str | None:
    """Retrieve the stored GitHub token (or ``None``)."""
    return asyncio.run(_get_token(db_dir))


def delete_token(db_dir: Path | None = None) -> bool:
    """Delete the stored GitHub token.  Returns ``True`` if it existed."""
    return asyncio.run(_delete_token(db_dir))
