"""Persistência: todo SQL do aplicativo fica aqui."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from typing import Iterator, Optional

from .models import Expense, Series

_SERIES_SQL = """
    SELECT s.id, s.name, s.amount_cents, s.kind, s.frequency, s.start_date,
           s.end_date, s.notes, c.name AS category
    FROM series s JOIN categories c ON c.id = s.category_id
"""

_EXPENSE_SQL = """
    SELECT e.id, e.name, e.amount_cents, e.due_date, e.notes, e.series_id,
           e.amount_overridden, e.paid_at, c.name AS category,
           s.kind AS series_kind, s.frequency
    FROM expenses e
    JOIN categories c ON c.id = e.category_id
    LEFT JOIN series s ON s.id = e.series_id
"""


def _to_date(value: Optional[str]) -> Optional[date]:
    return date.fromisoformat(value) if value else None


def _row_to_series(row: sqlite3.Row) -> Series:
    return Series(
        id=row["id"],
        name=row["name"],
        amount_cents=row["amount_cents"],
        kind=row["kind"],
        frequency=row["frequency"],
        start_date=_to_date(row["start_date"]),
        end_date=_to_date(row["end_date"]),
        category=row["category"],
        notes=row["notes"],
    )


def _row_to_expense(row: sqlite3.Row) -> Expense:
    return Expense(
        id=row["id"],
        name=row["name"],
        amount_cents=row["amount_cents"],
        due_date=_to_date(row["due_date"]),
        category=row["category"],
        notes=row["notes"],
        series_id=row["series_id"],
        series_kind=row["series_kind"],
        frequency=row["frequency"],
        amount_overridden=bool(row["amount_overridden"]),
        paid_at=row["paid_at"],
    )


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # ----- categorias -------------------------------------------------------
    def category_id(self, name: str) -> int:
        name = name.strip() or "Outros"
        self.conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
        row = self.conn.execute(
            "SELECT id FROM categories WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        return row["id"]

    def category_names(self) -> list[str]:
        rows = self.conn.execute("SELECT name FROM categories ORDER BY name COLLATE NOCASE")
        return [row["name"] for row in rows]

    # ----- séries -----------------------------------------------------------
    def insert_series(self, series: Series) -> int:
        cursor = self.conn.execute(
            """INSERT INTO series (name, amount_cents, kind, frequency, start_date,
                                   end_date, category_id, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                series.name,
                series.amount_cents,
                series.kind,
                series.frequency,
                series.start_date.isoformat(),
                series.end_date.isoformat() if series.end_date else None,
                self.category_id(series.category),
                series.notes,
            ),
        )
        return cursor.lastrowid

    def update_series(self, series: Series) -> None:
        self.conn.execute(
            """UPDATE series SET name = ?, amount_cents = ?, end_date = ?,
                                 category_id = ?, notes = ?
               WHERE id = ?""",
            (
                series.name,
                series.amount_cents,
                series.end_date.isoformat() if series.end_date else None,
                self.category_id(series.category),
                series.notes,
                series.id,
            ),
        )

    def get_series(self, series_id: int) -> Optional[Series]:
        row = self.conn.execute(_SERIES_SQL + " WHERE s.id = ?", (series_id,)).fetchone()
        return _row_to_series(row) if row else None

    def list_series(self, kind: Optional[str] = None) -> list[Series]:
        if kind:
            rows = self.conn.execute(_SERIES_SQL + " WHERE s.kind = ? ORDER BY s.name", (kind,))
        else:
            rows = self.conn.execute(_SERIES_SQL + " ORDER BY s.name")
        return [_row_to_series(row) for row in rows]

    def delete_series(self, series_id: int) -> None:
        """Remove a série. Ocorrências pagas viram contas avulsas (histórico preservado)."""
        self.conn.execute(
            "DELETE FROM expenses WHERE series_id = ? AND paid_at IS NULL", (series_id,)
        )
        self.conn.execute("UPDATE expenses SET series_id = NULL WHERE series_id = ?", (series_id,))
        self.conn.execute("DELETE FROM series_skips WHERE series_id = ?", (series_id,))
        self.conn.execute("DELETE FROM series WHERE id = ?", (series_id,))

    def update_unpaid_occurrences(
        self, series_id: int, since: date, name: str, category: str, notes: str, amount_cents: int
    ) -> None:
        """Propaga o modelo da série às ocorrências não pagas a partir de `since`.

        Valores alterados manualmente para um mês (amount_overridden) são preservados.
        """
        category_id = self.category_id(category)
        self.conn.execute(
            """UPDATE expenses SET name = ?, category_id = ?, notes = ?
               WHERE series_id = ? AND paid_at IS NULL AND due_date >= ?""",
            (name, category_id, notes, series_id, since.isoformat()),
        )
        self.conn.execute(
            """UPDATE expenses SET amount_cents = ?
               WHERE series_id = ? AND paid_at IS NULL AND amount_overridden = 0
                 AND due_date >= ?""",
            (amount_cents, series_id, since.isoformat()),
        )

    def delete_unpaid_occurrences_after(self, series_id: int, after: date) -> None:
        self.conn.execute(
            "DELETE FROM expenses WHERE series_id = ? AND paid_at IS NULL AND due_date > ?",
            (series_id, after.isoformat()),
        )

    def is_skipped(self, series_id: int, due: date) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM series_skips WHERE series_id = ? AND due_date = ?",
            (series_id, due.isoformat()),
        ).fetchone()
        return row is not None

    def add_skip(self, series_id: int, due: date) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO series_skips (series_id, due_date) VALUES (?, ?)",
            (series_id, due.isoformat()),
        )

    def insert_occurrence_if_missing(self, series: Series, due: date) -> None:
        self.conn.execute(
            """INSERT OR IGNORE INTO expenses
                   (name, amount_cents, due_date, category_id, notes, series_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                series.name,
                series.amount_cents,
                due.isoformat(),
                self.category_id(series.category),
                series.notes,
                series.id,
            ),
        )

    # ----- contas -----------------------------------------------------------
    def insert_expense(self, expense: Expense) -> int:
        cursor = self.conn.execute(
            """INSERT INTO expenses (name, amount_cents, due_date, category_id, notes,
                                     series_id, amount_overridden, paid_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                expense.name,
                expense.amount_cents,
                expense.due_date.isoformat(),
                self.category_id(expense.category),
                expense.notes,
                expense.series_id,
                int(expense.amount_overridden),
                expense.paid_at,
            ),
        )
        return cursor.lastrowid

    def update_expense(self, expense: Expense) -> None:
        self.conn.execute(
            """UPDATE expenses SET name = ?, amount_cents = ?, due_date = ?,
                                   category_id = ?, notes = ?, amount_overridden = ?
               WHERE id = ?""",
            (
                expense.name,
                expense.amount_cents,
                expense.due_date.isoformat(),
                self.category_id(expense.category),
                expense.notes,
                int(expense.amount_overridden),
                expense.id,
            ),
        )

    def attach_expense_to_series(self, expense_id: int, series_id: int) -> None:
        self.conn.execute(
            "UPDATE expenses SET series_id = ?, amount_overridden = 0 WHERE id = ?",
            (series_id, expense_id),
        )

    def set_paid_at(self, expense_id: int, paid_at: Optional[str]) -> None:
        self.conn.execute("UPDATE expenses SET paid_at = ? WHERE id = ?", (paid_at, expense_id))

    def get_expense(self, expense_id: int) -> Optional[Expense]:
        row = self.conn.execute(_EXPENSE_SQL + " WHERE e.id = ?", (expense_id,)).fetchone()
        return _row_to_expense(row) if row else None

    def delete_expense(self, expense_id: int) -> None:
        self.conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))

    def list_expenses(
        self,
        first: Optional[date] = None,
        last: Optional[date] = None,
        only_unique: bool = False,
    ) -> list[Expense]:
        clauses, params = [], []
        if first and last:
            clauses.append("e.due_date BETWEEN ? AND ?")
            params += [first.isoformat(), last.isoformat()]
        if only_unique:
            clauses.append("e.series_id IS NULL")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self.conn.execute(
            _EXPENSE_SQL + where + " ORDER BY e.due_date, e.id", params
        )
        return [_row_to_expense(row) for row in rows]

    def find_similar(self, name: str, due: date, amount_cents: int) -> Optional[Expense]:
        row = self.conn.execute(
            _EXPENSE_SQL
            + " WHERE e.due_date = ? AND e.amount_cents = ? AND lower(e.name) = lower(?)",
            (due.isoformat(), amount_cents, name.strip()),
        ).fetchone()
        return _row_to_expense(row) if row else None
