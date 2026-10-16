"""Conexão SQLite, esquema, backup e restauração."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_CATEGORIES = (
    "Moradia",
    "Contas da casa",
    "Alimentação",
    "Transporte",
    "Saúde",
    "Lazer",
    "Assinaturas",
    "Outros",
)

REQUIRED_TABLES = {"categories", "series", "expenses", "series_skips"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS series (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
    kind         TEXT NOT NULL CHECK (kind IN ('fixo', 'recorrente')),
    frequency    TEXT NOT NULL CHECK (frequency IN ('semanal', 'mensal', 'anual')),
    start_date   TEXT NOT NULL,
    end_date     TEXT,
    category_id  INTEGER NOT NULL REFERENCES categories (id),
    notes        TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS expenses (
    id                INTEGER PRIMARY KEY,
    name              TEXT NOT NULL,
    amount_cents      INTEGER NOT NULL CHECK (amount_cents >= 0),
    due_date          TEXT NOT NULL,
    category_id       INTEGER NOT NULL REFERENCES categories (id),
    notes             TEXT NOT NULL DEFAULT '',
    series_id         INTEGER REFERENCES series (id),
    amount_overridden INTEGER NOT NULL DEFAULT 0,
    paid_at           TEXT,
    UNIQUE (series_id, due_date)  -- impede cobranças duplicadas da mesma série
);

CREATE TABLE IF NOT EXISTS series_skips (
    series_id INTEGER NOT NULL REFERENCES series (id),
    due_date  TEXT NOT NULL,
    PRIMARY KEY (series_id, due_date)
);

CREATE INDEX IF NOT EXISTS idx_expenses_due_date ON expenses (due_date);
"""


def default_db_path() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home()) / "OrganizadorFinanceiro"
    base.mkdir(parents=True, exist_ok=True)
    return base / "financas.db"


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT OR IGNORE INTO categories (name) VALUES (?)",
        [(name,) for name in DEFAULT_CATEGORIES],
    )
    conn.commit()
    return conn


def backup(conn: sqlite3.Connection, destination: str | Path) -> None:
    with sqlite3.connect(str(destination)) as target:
        conn.backup(target)
    target.close()


def restore(conn: sqlite3.Connection, source: str | Path) -> None:
    """Substitui todos os dados pelos de um arquivo de backup validado."""
    uri = Path(source).resolve().as_uri() + "?mode=ro"
    try:
        source_conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise ValueError("Não foi possível abrir o arquivo de backup.") from exc
    try:
        tables = {
            row[0] for row in source_conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        if not REQUIRED_TABLES.issubset(tables):
            raise ValueError("O arquivo não é um backup válido deste aplicativo.")
        if source_conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("O arquivo de backup está corrompido.")
        source_conn.backup(conn)
    except sqlite3.DatabaseError as exc:
        raise ValueError("O arquivo de backup não pôde ser lido.") from exc
    finally:
        source_conn.close()
    conn.executescript(SCHEMA)  # garante o esquema atual após a restauração
