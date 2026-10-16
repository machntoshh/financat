"""Formatação e leitura de valores e datas no padrão brasileiro."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def format_money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    reais, centavos = divmod(abs(cents), 100)
    return f"{sign}R$ {reais:,}".replace(",", ".") + f",{centavos:02d}"


def parse_money(text: str) -> int:
    """Converte texto como '1.234,56', '1234.5' ou 'R$ 90' em centavos."""
    raw = text.strip().replace("R$", "").replace(" ", "")
    if not raw:
        raise ValueError("Informe o valor da conta.")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise ValueError(f"Valor inválido: '{text}'.") from None
    if not value.is_finite():
        raise ValueError(f"Valor inválido: '{text}'.")
    if value < 0:
        raise ValueError("O valor não pode ser negativo.")
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def due_label(due: date, today: date) -> str:
    """Expressão amigável para o vencimento, sem esconder a data exata."""
    days = (due - today).days
    if days < 0:
        late = -days
        return f"Venceu há {late} dia{'s' if late > 1 else ''}"
    if days == 0:
        return "Vence hoje"
    if days == 1:
        return "Vence amanhã"
    return f"Vence em {days} dias"
