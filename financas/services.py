"""Regras de negócio. A interface conversa apenas com FinanceService."""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable, Optional

from . import db
from .formatting import format_date
from .models import (
    FREQUENCIES,
    FREQUENCY_LABELS,
    KIND_LABELS,
    SERIES_KINDS,
    STATUS_LABELS,
    STATUS_PENDENTE,
    STATUS_VENCIDO,
    Expense,
    Series,
)
from .recurrence import due_dates_between
from .repository import Repository

FILTERS = {
    "todas": "Todas",
    "pendentes": "Pendentes",
    "pagas": "Pagas",
    "vencidas": "Vencidas",
    "fixos": "Fixos",
    "recorrentes": "Recorrentes",
}

SERIES_LOOKAHEAD_DAYS = 366 * 3


class ValidationError(ValueError):
    """Erro esperado causado por dados inválidos; a interface mostra a mensagem ao usuário."""


@dataclass
class MonthSummary:
    year: int
    month: int
    items: list[Expense] = field(default_factory=list)
    total_cents: int = 0
    paid_cents: int = 0
    pending_cents: int = 0
    next_due: Optional[Expense] = None


def month_bounds(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    return first, nxt - timedelta(days=1)


def apply_filter(items: list[Expense], key: str, today: date) -> list[Expense]:
    if key == "pendentes":
        return [e for e in items if e.status(today) == STATUS_PENDENTE]
    if key == "pagas":
        return [e for e in items if e.is_paid]
    if key == "vencidas":
        return [e for e in items if e.status(today) == STATUS_VENCIDO]
    if key == "fixos":
        return [e for e in items if e.series_kind == "fixo"]
    if key == "recorrentes":
        return [e for e in items if e.series_kind == "recorrente"]
    return list(items)


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValidationError("Informe o nome da conta.")
    return cleaned


def _check_amount(amount_cents: int) -> None:
    if amount_cents <= 0:
        raise ValidationError("O valor deve ser maior que zero.")


def _check_schedule(kind: str, frequency: str, start: date, end: Optional[date]) -> None:
    if kind not in SERIES_KINDS:
        raise ValidationError("Tipo de gasto inválido.")
    if frequency not in FREQUENCIES:
        raise ValidationError("Frequência inválida.")
    if end is not None and end < start:
        raise ValidationError("A data de término deve ser depois da data de início.")


class FinanceService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        today: Callable[[], date] = date.today,
        now: Callable[[], datetime] = datetime.now,
    ):
        self.conn = conn
        self.repo = Repository(conn)
        self._today = today
        self._now = now

    # ----- consultas --------------------------------------------------------
    def today(self) -> date:
        return self._today()

    def categories(self) -> list[str]:
        return self.repo.category_names()

    def month_summary(self, year: int, month: int) -> MonthSummary:
        self.ensure_month(year, month)
        first, last = month_bounds(year, month)
        items = self.repo.list_expenses(first, last)
        summary = MonthSummary(year=year, month=month, items=items)
        summary.total_cents = sum(e.amount_cents for e in items)
        summary.paid_cents = sum(e.amount_cents for e in items if e.is_paid)
        summary.pending_cents = summary.total_cents - summary.paid_cents
        unpaid = [e for e in items if not e.is_paid]
        summary.next_due = min(unpaid, key=lambda e: (e.due_date, e.id), default=None)
        return summary

    def unique_expenses(self) -> list[Expense]:
        return self.repo.list_expenses(only_unique=True)

    def list_series(self, kind: str) -> list[Series]:
        return self.repo.list_series(kind)

    def series_next_due(self, series: Series) -> Optional[date]:
        """Próxima ocorrência não ignorada a partir de hoje."""
        today = self.today()
        upper = today + timedelta(days=SERIES_LOOKAHEAD_DAYS)
        if series.end_date:
            upper = min(upper, series.end_date)
        for due in due_dates_between(series.start_date, series.frequency, today, upper):
            if not self.repo.is_skipped(series.id, due):
                return due
        return None

    def get_expense(self, expense_id: int) -> Expense:
        expense = self.repo.get_expense(expense_id)
        if expense is None:
            raise ValidationError("Esta conta não existe mais.")
        return expense

    def get_series(self, series_id: int) -> Series:
        series = self.repo.get_series(series_id)
        if series is None:
            raise ValidationError("Esta série não existe mais.")
        return series

    def find_duplicate(self, name: str, due: date, amount_cents: int) -> Optional[Expense]:
        return self.repo.find_similar(name, due, amount_cents)

    # ----- geração de ocorrências ------------------------------------------
    def ensure_month(self, year: int, month: int) -> None:
        """Cria as ocorrências das séries no mês (idempotente: nunca duplica)."""
        first, last = month_bounds(year, month)
        with self.repo.transaction():
            for series in self.repo.list_series():
                upper = min(last, series.end_date) if series.end_date else last
                for due in due_dates_between(series.start_date, series.frequency, first, upper):
                    if not self.repo.is_skipped(series.id, due):
                        self.repo.insert_occurrence_if_missing(series, due)

    # ----- contas avulsas e ocorrências ------------------------------------
    def add_expense(
        self,
        name: str,
        amount_cents: int,
        due: date,
        category: str = "Outros",
        notes: str = "",
        kind: str = "unico",
        frequency: str = "mensal",
        end_date: Optional[date] = None,
    ) -> None:
        name = _clean_name(name)
        _check_amount(amount_cents)
        with self.repo.transaction():
            if kind == "unico":
                self.repo.insert_expense(
                    Expense(name=name, amount_cents=amount_cents, due_date=due,
                            category=category, notes=notes.strip())
                )
                return
            _check_schedule(kind, frequency, due, end_date)
            series = Series(
                name=name, amount_cents=amount_cents, kind=kind, frequency=frequency,
                start_date=due, end_date=end_date, category=category, notes=notes.strip(),
            )
            series.id = self.repo.insert_series(series)
            self.repo.insert_occurrence_if_missing(series, due)

    def update_expense(
        self,
        expense_id: int,
        name: str,
        amount_cents: int,
        due: date,
        category: str,
        notes: str,
    ) -> None:
        expense = self.get_expense(expense_id)
        name = _clean_name(name)
        _check_amount(amount_cents)
        if expense.series_id is not None:
            if due != expense.due_date:
                raise ValidationError(
                    "A data de uma ocorrência de série não pode ser alterada. Edite a série."
                )
            # Alterar o valor vale só para este mês; os demais meses continuam iguais.
            if amount_cents != expense.amount_cents:
                expense.amount_overridden = True
        expense.name = name
        expense.amount_cents = amount_cents
        expense.due_date = due
        expense.category = category
        expense.notes = notes.strip()
        with self.repo.transaction():
            self.repo.update_expense(expense)

    def set_paid(self, expense_id: int, paid: bool) -> bool:
        """Registra ou desfaz o pagamento. Retorna True só quando a conta passou a 'paga'."""
        expense = self.get_expense(expense_id)
        if expense.is_paid == paid:
            return False
        paid_at = self._now().isoformat(timespec="seconds") if paid else None
        with self.repo.transaction():
            self.repo.set_paid_at(expense_id, paid_at)
        return paid

    def delete_expense(self, expense_id: int) -> None:
        expense = self.repo.get_expense(expense_id)
        if expense is None:
            return
        with self.repo.transaction():
            if expense.series_id is not None:
                # Ocorrência excluída não pode voltar na próxima geração do mês.
                self.repo.add_skip(expense.series_id, expense.due_date)
            self.repo.delete_expense(expense_id)

    def convert_to_series(
        self,
        expense_id: int,
        kind: str,
        frequency: str,
        end_date: Optional[date] = None,
    ) -> None:
        """Transforma uma conta avulsa em fixa ou recorrente, mantendo o pagamento já feito."""
        expense = self.get_expense(expense_id)
        if expense.series_id is not None:
            raise ValidationError("Esta conta já faz parte de uma série.")
        _check_schedule(kind, frequency, expense.due_date, end_date)
        with self.repo.transaction():
            series = Series(
                name=expense.name, amount_cents=expense.amount_cents, kind=kind,
                frequency=frequency, start_date=expense.due_date, end_date=end_date,
                category=expense.category, notes=expense.notes,
            )
            series.id = self.repo.insert_series(series)
            self.repo.attach_expense_to_series(expense_id, series.id)

    # ----- séries -----------------------------------------------------------
    def update_series(
        self,
        series_id: int,
        name: str,
        amount_cents: int,
        category: str,
        notes: str,
        end_date: Optional[date],
    ) -> None:
        """Atualiza o modelo da série. Só mexe em contas não pagas do mês atual em diante."""
        series = self.get_series(series_id)
        name = _clean_name(name)
        _check_amount(amount_cents)
        _check_schedule(series.kind, series.frequency, series.start_date, end_date)
        series.name = name
        series.amount_cents = amount_cents
        series.category = category
        series.notes = notes.strip()
        series.end_date = end_date
        since = self.today().replace(day=1)
        with self.repo.transaction():
            self.repo.update_series(series)
            self.repo.update_unpaid_occurrences(
                series_id, since, series.name, series.category, series.notes, series.amount_cents
            )
            if end_date:
                self.repo.delete_unpaid_occurrences_after(series_id, end_date)

    def delete_series(self, series_id: int) -> None:
        with self.repo.transaction():
            self.repo.delete_series(series_id)

    # ----- backup, restauração e exportação --------------------------------
    def backup(self, destination: str) -> None:
        db.backup(self.conn, destination)

    def restore(self, source: str, safety_copy: Optional[str] = None) -> None:
        if safety_copy:
            self.backup(safety_copy)
        db.restore(self.conn, source)

    def export_csv(self, destination: str) -> int:
        today = self.today()
        for offset in range(-12, 13):  # inclui as ocorrências programadas de 1 ano para trás e à frente
            year, month = divmod(today.month - 1 + offset, 12)
            self.ensure_month(today.year + year, month + 1)
        rows = self.repo.list_expenses()
        with open(destination, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow([
                "Vencimento", "Conta", "Categoria", "Tipo", "Frequência",
                "Valor", "Status", "Pago em", "Observações",
            ])
            for e in rows:
                paid_on = ""
                if e.paid_at:
                    paid_on = datetime.fromisoformat(e.paid_at).strftime("%d/%m/%Y %H:%M")
                writer.writerow([
                    format_date(e.due_date),
                    e.name,
                    e.category,
                    KIND_LABELS[e.kind],
                    FREQUENCY_LABELS.get(e.frequency or "", ""),
                    f"{e.amount_cents / 100:.2f}".replace(".", ","),
                    STATUS_LABELS[e.status(today)],
                    paid_on,
                    e.notes,
                ])
        return len(rows)
