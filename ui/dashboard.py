"""Dashboard mensal: indicadores, filtros e lista de contas do mês."""

from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from financas.formatting import due_label, format_date, format_money
from financas.models import KIND_LABELS, STATUS_LABELS, Expense
from financas.services import FILTERS, FinanceService, MonthSummary, ValidationError, apply_filter

from .common import MONTH_NAMES, status_color
from .expense_dialog import open_expense_dialog


class StatCard(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.title = QLabel(title)
        self.title.setObjectName("statTitle")
        self.value = QLabel("—")
        self.value.setObjectName("statValue")
        self.value.setWordWrap(True)
        self.detail = QLabel("")
        self.detail.setObjectName("muted")
        self.detail.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)
        layout.addStretch()

    def set_values(self, value: str, detail: str = "", color: str | None = None) -> None:
        self.value.setText(value)
        self.detail.setText(detail)
        style = f"color: {color};" if color else ""
        self.value.setStyleSheet(style)


class ExpenseRow(QFrame):
    toggle_paid = Signal(int, bool)
    edit_requested = Signal(object)

    def __init__(self, expense: Expense, today: date, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.expense = expense
        status = expense.status(today)
        color = status_color(status)

        bar = QFrame()
        bar.setFixedWidth(4)
        bar.setStyleSheet(f"background: {color}; border-radius: 2px;")

        name = QLabel(expense.name)
        name.setStyleSheet("font-size: 14px; font-weight: 600;" + (" color: #8E8E8E;" if expense.is_paid else ""))
        meta_parts = [expense.category]
        if expense.series_kind:
            meta_parts.append(KIND_LABELS[expense.series_kind])
        if not expense.is_paid:
            meta_parts.append(due_label(expense.due_date, today))
        meta_parts.append(format_date(expense.due_date))
        meta = QLabel(" · ".join(meta_parts))
        meta.setObjectName("muted")
        meta.setWordWrap(True)
        name.setWordWrap(True)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.addWidget(name)
        text_col.addWidget(meta)

        amount = QLabel(format_money(expense.amount_cents))
        amount.setStyleSheet("font-size: 15px; font-weight: 600;")
        amount.setMinimumWidth(110)
        amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        badge = QLabel(STATUS_LABELS[status])
        badge.setStyleSheet(f"color: {color}; font-weight: 600;")
        badge.setMinimumWidth(78)
        badge.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if expense.is_paid:
            action = QPushButton("Desfazer")
            action.setObjectName("rowAction")
            action.setToolTip("Voltar a conta para pendente")
        else:
            action = QPushButton("Marcar como paga")
            action.setObjectName("rowPay")
        action.clicked.connect(lambda: self.toggle_paid.emit(expense.id, not expense.is_paid))

        edit = QPushButton("Editar")
        edit.setObjectName("rowAction")
        edit.clicked.connect(lambda: self.edit_requested.emit(expense))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 12, 16, 12)
        layout.setSpacing(14)
        layout.addWidget(bar)
        layout.addLayout(text_col, 1)
        layout.addWidget(amount)
        layout.addWidget(badge)
        layout.addWidget(action)
        layout.addWidget(edit)


class DashboardPage(QWidget):
    data_changed = Signal(str)  # mensagem curta para feedback
    payment_made = Signal()

    def __init__(self, service: FinanceService, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        today = service.today()
        self.year, self.month = today.year, today.month
        self._summary: MonthSummary | None = None
        self._filter = "todas"

        self.title = QLabel()
        self.title.setObjectName("title")
        prev_btn = QPushButton("‹")
        prev_btn.setFixedWidth(40)
        prev_btn.setToolTip("Mês anterior")
        prev_btn.clicked.connect(lambda: self._move_month(-1))
        next_btn = QPushButton("›")
        next_btn.setFixedWidth(40)
        next_btn.setToolTip("Próximo mês")
        next_btn.clicked.connect(lambda: self._move_month(1))
        today_btn = QPushButton("Hoje")
        today_btn.clicked.connect(self._go_today)
        add_btn = QPushButton("+ Adicionar conta")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._add_account)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self.title)
        header.addSpacing(12)
        header.addWidget(prev_btn)
        header.addWidget(next_btn)
        header.addWidget(today_btn)
        header.addStretch()
        header.addWidget(add_btn)

        self.stat_total = StatCard("Total do mês")
        self.stat_paid = StatCard("Já pago")
        self.stat_pending = StatCard("Pendente")
        self.stat_next = StatCard("Próximo vencimento")
        stats = QHBoxLayout()
        stats.setSpacing(12)
        for card in (self.stat_total, self.stat_paid, self.stat_pending, self.stat_next):
            stats.addWidget(card, 1)

        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)
        filters = QHBoxLayout()
        filters.setSpacing(6)
        for key, label in FILTERS.items():
            button = QPushButton(label)
            button.setObjectName("pill")
            button.setCheckable(True)
            button.setChecked(key == self._filter)
            button.clicked.connect(lambda _checked=False, k=key: self._set_filter(k))
            self.filter_group.addButton(button)
            filters.addWidget(button)
        filters.addStretch()

        self.list_host = QWidget()
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 8, 0)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.list_host)

        self.empty_box = QWidget()
        empty_layout = QVBoxLayout(self.empty_box)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_text = QLabel()
        self.empty_text.setObjectName("muted")
        self.empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_button = QPushButton("+ Adicionar a primeira conta")
        empty_button.setObjectName("primary")
        empty_button.clicked.connect(self._add_account)
        empty_layout.addWidget(self.empty_text)
        empty_layout.addWidget(empty_button, 0, Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(16)
        layout.addLayout(header)
        layout.addLayout(stats)
        layout.addLayout(filters)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.empty_box)
        self.empty_box.hide()

        self.refresh()

    # ----- navegação --------------------------------------------------------
    def _move_month(self, delta: int) -> None:
        month = self.month + delta
        self.year += (month - 1) // 12
        self.month = (month - 1) % 12 + 1
        self.refresh()

    def _go_today(self) -> None:
        today = self.service.today()
        self.year, self.month = today.year, today.month
        self.refresh()

    def _set_filter(self, key: str) -> None:
        self._filter = key
        self.refresh()

    def _add_account(self) -> None:
        if open_expense_dialog(self.service, self):
            self.data_changed.emit("Conta adicionada")

    # ----- atualização ------------------------------------------------------
    def refresh(self) -> None:
        try:
            self._summary = self.service.month_summary(self.year, self.month)
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "Erro ao carregar", str(exc))
            return
        summary = self._summary
        today = self.service.today()
        self.title.setText(f"{MONTH_NAMES[self.month - 1]} de {self.year}")

        self.stat_total.set_values(format_money(summary.total_cents),
                                   f"{len(summary.items)} conta(s) no mês")
        self.stat_paid.set_values(format_money(summary.paid_cents), "quitado",
                                  color=status_color("pago"))
        self.stat_pending.set_values(format_money(summary.pending_cents), "ainda a pagar",
                                     color=status_color("pendente"))
        nxt = summary.next_due
        if nxt:
            self.stat_next.set_values(
                nxt.name, f"{format_money(nxt.amount_cents)} · {due_label(nxt.due_date, today)}",
                color=status_color(nxt.status(today)),
            )
        else:
            self.stat_next.set_values("Nada pendente", "Tudo em dia neste mês")

        self._rebuild_rows(today)

    def _rebuild_rows(self, today: date) -> None:
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)  # sai da árvore já; deleteLater libera depois
                widget.deleteLater()

        items = self._summary.items
        if not items:
            self.empty_text.setText(
                "Nenhuma conta neste mês.\nAdicione contas para acompanhar seus pagamentos."
            )
            self.empty_box.show()
            return
        self.empty_box.hide()

        visible = apply_filter(items, self._filter, today)
        if not visible:
            hint = QLabel("Nenhuma conta com este filtro neste mês.")
            hint.setObjectName("muted")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.insertWidget(0, hint)
            return
        for index, expense in enumerate(visible):
            row = ExpenseRow(expense, today)
            row.toggle_paid.connect(self._toggle_paid)
            row.edit_requested.connect(self._edit)
            self.list_layout.insertWidget(index, row)

    # ----- ações ------------------------------------------------------------
    def _toggle_paid(self, expense_id: int, paid: bool) -> None:
        try:
            became_paid = self.service.set_paid(expense_id, paid)
        except (ValidationError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Não foi possível atualizar", str(exc))
            return
        if became_paid:
            # Só comemora depois que o pagamento foi gravado com sucesso.
            self.payment_made.emit()
            self.data_changed.emit("Pagamento registrado")
        else:
            self.data_changed.emit("Conta marcada como pendente")

    def _edit(self, expense: Expense) -> None:
        if open_expense_dialog(self.service, self, expense=expense):
            self.data_changed.emit("Conta atualizada")
