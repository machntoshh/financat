"""Tela 'Contas a pagar': todas as contas avulsas, de todos os meses."""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from financas.formatting import format_date, format_money
from financas.models import STATUS_LABELS, Expense
from financas.services import FILTERS, FinanceService, ValidationError, apply_filter

from .common import confirm, make_table, status_color
from .expense_dialog import open_expense_dialog


class BillsPage(QWidget):
    data_changed = Signal(str)
    payment_made = Signal()

    def __init__(self, service: FinanceService, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service

        title = QLabel("Contas a pagar")
        title.setObjectName("title")
        subtitle = QLabel("Contas avulsas de todos os meses. Para fixas e recorrentes, veja a barra lateral.")
        subtitle.setObjectName("muted")

        self.filter_combo = QComboBox()
        for key in ("todas", "pendentes", "pagas", "vencidas"):
            self.filter_combo.addItem(FILTERS[key], key)
        self.filter_combo.currentIndexChanged.connect(lambda _i: self.refresh())

        add_btn = QPushButton("+ Adicionar conta")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._add)
        self.pay_btn = QPushButton("Marcar como paga")
        self.pay_btn.clicked.connect(self._toggle_selected)
        edit_btn = QPushButton("Editar")
        edit_btn.clicked.connect(self._edit_selected)
        delete_btn = QPushButton("Excluir")
        delete_btn.setObjectName("danger")
        delete_btn.clicked.connect(self._delete_selected)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        toolbar.addWidget(QLabel("Mostrar:"))
        toolbar.addWidget(self.filter_combo)
        toolbar.addStretch()
        toolbar.addWidget(self.pay_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(delete_btn)
        toolbar.addWidget(add_btn)

        self.table = make_table(["Conta", "Categoria", "Vencimento", "Valor", "Status"])
        self.table.doubleClicked.connect(lambda _index: self._edit_selected())
        self.table.itemSelectionChanged.connect(self._update_pay_label)

        self.empty_hint = QLabel("Nenhuma conta por aqui. Use “+ Adicionar conta” para começar.")
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
        selected_id = self._selected_id()
        today = self.service.today()
        items = apply_filter(self.service.unique_expenses(), self.filter_combo.currentData(), today)
        self.table.setRowCount(len(items))
        for row, expense in enumerate(items):
            self._fill_row(row, expense, today)
            if expense.id == selected_id:
                self.table.selectRow(row)
        self.empty_hint.setVisible(not items)
        self._update_pay_label()

    def _fill_row(self, row: int, expense: Expense, today) -> None:
        status = expense.status(today)
        values = [
            expense.name,
            expense.category,
            format_date(expense.due_date),
            format_money(expense.amount_cents),
            STATUS_LABELS[status],
        ]
        for column, text in enumerate(values):
            cell = QTableWidgetItem(text)
            cell.setData(Qt.ItemDataRole.UserRole, expense.id)
            if column == 4:
                cell.setForeground(QColor(status_color(status)))
            if column == 3:
                cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, column, cell)

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _selected_expense(self) -> Expense | None:
        expense_id = self._selected_id()
        if expense_id is None:
            QMessageBox.information(self, "Nenhuma conta selecionada", "Clique em uma conta na lista primeiro.")
            return None
        try:
            return self.service.get_expense(expense_id)
        except ValidationError as exc:
            QMessageBox.warning(self, "Conta indisponível", str(exc))
            self.refresh()
            return None

    def _update_pay_label(self) -> None:
        expense_id = self._selected_id()
        paid = False
        if expense_id is not None:
            try:
                paid = self.service.get_expense(expense_id).is_paid
            except ValidationError:
                paid = False
        self.pay_btn.setText("Desfazer pagamento" if paid else "Marcar como paga")

    # ----- ações ------------------------------------------------------------
    def _add(self) -> None:
        if open_expense_dialog(self.service, self):
            self.data_changed.emit("Conta adicionada")

    def _edit_selected(self) -> None:
        expense = self._selected_expense()
        if expense and open_expense_dialog(self.service, self, expense=expense):
            self.data_changed.emit("Conta atualizada")

    def _toggle_selected(self) -> None:
        expense = self._selected_expense()
        if expense is None:
            return
        try:
            became_paid = self.service.set_paid(expense.id, not expense.is_paid)
        except (ValidationError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Não foi possível atualizar", str(exc))
            return
        if became_paid:
            self.payment_made.emit()
            self.data_changed.emit("Pagamento registrado")
        else:
            self.data_changed.emit("Conta marcada como pendente")

    def _delete_selected(self) -> None:
        expense = self._selected_expense()
        if expense is None:
            return
        if not confirm(self, "Confirmar exclusão", f"Excluir '{expense.name}'?"):
            return
        try:
            self.service.delete_expense(expense.id)
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "Erro ao excluir", str(exc))
            return
        self.data_changed.emit("Conta excluída")
