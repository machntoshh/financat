"""Telas 'Gastos fixos' e 'Gastos recorrentes': modelos de série."""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from financas.formatting import format_date, format_money
from financas.models import FREQUENCY_LABELS, Series
from financas.services import FinanceService, ValidationError

from .common import confirm, make_table
from .expense_dialog import open_expense_dialog

PAGE_TEXT = {
    "fixo": (
        "Gastos fixos",
        "Despesas previsíveis do orçamento, como aluguel, internet e academia.",
    ),
    "recorrente": (
        "Gastos recorrentes",
        "Pagamentos que se repetem, como assinaturas, streaming e mensalidades.",
    ),
}


class SeriesPage(QWidget):
    data_changed = Signal(str)
    payment_made = Signal()  # não usado aqui; mantém a mesma interface das outras telas

    def __init__(self, service: FinanceService, kind: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self.kind = kind
        self._series_ids: list[int] = []

        heading, description = PAGE_TEXT[kind]
        title = QLabel(heading)
        title.setObjectName("title")
        subtitle = QLabel(description + " As próximas cobranças são geradas automaticamente.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)

        add_btn = QPushButton("+ Adicionar")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._add)
        edit_btn = QPushButton("Editar")
        edit_btn.clicked.connect(self._edit_selected)
        delete_btn = QPushButton("Excluir")
        delete_btn.setObjectName("danger")
        delete_btn.clicked.connect(self._delete_selected)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        toolbar.addStretch()
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(delete_btn)
        toolbar.addWidget(add_btn)

        self.table = make_table(
            ["Nome", "Valor", "Categoria", "Frequência", "Início", "Término", "Próximo vencimento"]
        )
        self.table.doubleClicked.connect(lambda _index: self._edit_selected())

        self.empty_hint = QLabel("Nada cadastrado aqui ainda. Use “+ Adicionar” para criar o primeiro.")
        self.empty_hint.setObjectName("muted")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(toolbar)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.empty_hint)

        self.refresh()

    # ----- dados ------------------------------------------------------------
    def refresh(self) -> None:
        selected_id = self._selected_series_id()
        series_list = self.service.list_series(self.kind)
        self._series_ids = [s.id for s in series_list]
        self.table.setRowCount(len(series_list))
        for row, series in enumerate(series_list):
            for column, text in enumerate(self._values(series)):
                cell = QTableWidgetItem(text)
                cell.setData(Qt.ItemDataRole.UserRole, series.id)
                if column == 1:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, cell)
            if series.id == selected_id:
                self.table.selectRow(row)
        self.empty_hint.setVisible(not series_list)

    def _values(self, series: Series) -> list[str]:
        nxt = self.service.series_next_due(series)
        return [
            series.name,
            format_money(series.amount_cents),
            series.category,
            FREQUENCY_LABELS[series.frequency],
            format_date(series.start_date),
            format_date(series.end_date) if series.end_date else "Sem término",
            format_date(nxt) if nxt else "—",
        ]

    def _selected_series_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _selected_series(self) -> Series | None:
        series_id = self._selected_series_id()
        if series_id is None:
            QMessageBox.information(self, "Nada selecionado", "Clique em um item da lista primeiro.")
            return None
        try:
            return self.service.get_series(series_id)
        except ValidationError as exc:
            QMessageBox.warning(self, "Indisponível", str(exc))
            self.refresh()
            return None

    # ----- ações ------------------------------------------------------------
    def _add(self) -> None:
        if open_expense_dialog(self.service, self, default_kind=self.kind):
            self.data_changed.emit("Cadastro salvo")

    def _edit_selected(self) -> None:
        series = self._selected_series()
        if series and open_expense_dialog(self.service, self, series=series):
            self.data_changed.emit("Série atualizada")

    def _delete_selected(self) -> None:
        series = self._selected_series()
        if series is None:
            return
        text = (
            f"Excluir '{series.name}'?\n\nAs contas não pagas serão removidas. "
            "As já pagas continuam no histórico como contas avulsas."
        )
        if not confirm(self, "Excluir série", text):
            return
        try:
            self.service.delete_series(series.id)
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "Erro ao excluir", str(exc))
            return
        self.data_changed.emit("Série excluída")
