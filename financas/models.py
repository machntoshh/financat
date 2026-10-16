"""Entidades do domínio financeiro."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

FREQUENCIES = ("semanal", "mensal", "anual")
SERIES_KINDS = ("fixo", "recorrente")

FREQUENCY_LABELS = {"semanal": "Semanal", "mensal": "Mensal", "anual": "Anual"}
KIND_LABELS = {"unico": "Única", "fixo": "Fixa", "recorrente": "Recorrente"}

STATUS_PAGO = "pago"
STATUS_PENDENTE = "pendente"
STATUS_VENCIDO = "vencido"
STATUS_LABELS = {STATUS_PAGO: "Paga", STATUS_PENDENTE: "Pendente", STATUS_VENCIDO: "Vencida"}


@dataclass
class Series:
    """Modelo de uma despesa fixa ou recorrente. Gera ocorrências mensais/semanais/anuais."""

    name: str
    amount_cents: int
    kind: str  # "fixo" ou "recorrente"
    frequency: str  # "semanal", "mensal" ou "anual"
    start_date: date
    end_date: Optional[date] = None
    category: str = "Outros"
    notes: str = ""
    id: Optional[int] = None


@dataclass
class Expense:
    """Uma conta a pagar. Pode ser avulsa (series_id is None) ou uma ocorrência de série."""

    name: str
    amount_cents: int
    due_date: date
    category: str = "Outros"
    notes: str = ""
    series_id: Optional[int] = None
    series_kind: Optional[str] = None  # "fixo" / "recorrente" quando pertence a série
    frequency: Optional[str] = None
    amount_overridden: bool = False  # valor alterado só para este mês
    paid_at: Optional[str] = None  # ISO datetime quando paga
    id: Optional[int] = None

    @property
    def kind(self) -> str:
        return self.series_kind or "unico"

    @property
    def is_paid(self) -> bool:
        return self.paid_at is not None

    def status(self, today: date) -> str:
        if self.is_paid:
            return STATUS_PAGO
        if self.due_date < today:
            return STATUS_VENCIDO
        return STATUS_PENDENTE
