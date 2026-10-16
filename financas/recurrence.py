"""Cálculo puro das datas de vencimento de uma série."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta


def _clipped(year: int, month: int, day: int) -> date:
    """Dia do mês, limitado ao último dia (ex.: 31 de fevereiro vira 28/29)."""
    return date(year, month, min(day, monthrange(year, month)[1]))


def due_dates_between(start: date, frequency: str, first: date, last: date) -> list[date]:
    """Datas de vencimento de uma série que caem no intervalo [first, last]."""
    if last < first or last < start:
        return []

    result: list[date] = []
    if frequency == "semanal":
        current = start
        if first > start:
            weeks_ahead = ((first - start).days + 6) // 7  # arredonda para cima
            current = start + timedelta(weeks=weeks_ahead)
        while current <= last:
            result.append(current)
            current += timedelta(days=7)
        return result

    if frequency not in ("mensal", "anual"):
        raise ValueError(f"Frequência desconhecida: {frequency}")

    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        if frequency == "mensal" or month == start.month:
            candidate = _clipped(year, month, start.day)
            if start <= candidate <= last and candidate >= first:
                result.append(candidate)
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return result
