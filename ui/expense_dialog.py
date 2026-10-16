"""Formulário de cadastro/edição de conta, série fixa/recorrente e ocorrências."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from financas.formatting import format_money, parse_money
from financas.models import FREQUENCY_LABELS, KIND_LABELS, Expense, Series
from financas.services import FinanceService, ValidationError

MODE_NEW_OR_ONE_OFF = "avulsa"
MODE_OCCURRENCE = "ocorrencia"
MODE_SERIES = "serie"


def _to_qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)


class ExpenseDialog(QDialog):
    def __init__(
        self,
        service: FinanceService,
        parent: Optional[QWidget] = None,
        expense: Optional[Expense] = None,
        series: Optional[Series] = None,
        default_kind: str = "unico",
    ):
        super().__init__(parent)
        self.service = service
        self.expense = expense
        self.series = series
        self.deleted = False

        if series is not None:
            self.mode = MODE_SERIES
            self.setWindowTitle("Editar série")
        elif expense is not None and expense.series_id is not None:
            self.mode = MODE_OCCURRENCE
            self.setWindowTitle("Editar conta")
        else:
            self.mode = MODE_NEW_OR_ONE_OFF
            self.setWindowTitle("Editar conta" if expense else "Nova conta")

        self.setModal(True)
        self.setMinimumWidth(440)
        self._build()
        self._fill(default_kind)
        self._update_enabled()

    # ----- montagem ---------------------------------------------------------
    def _build(self) -> None:
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Ex.: Conta de luz")
        self.amount_edit = QLineEdit()
        self.amount_edit.setPlaceholderText("0,00")
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems(self.service.categories())
        self.kind_combo = QComboBox()
        for key in ("unico", "fixo", "recorrente"):
            self.kind_combo.addItem(KIND_LABELS[key], key)
        self.kind_combo.currentIndexChanged.connect(self._update_enabled)
        self.frequency_combo = QComboBox()
        for key, label in FREQUENCY_LABELS.items():
            self.frequency_combo.addItem(label, key)
        self.end_check = QCheckBox("Tem data de término")
        self.end_check.toggled.connect(self._update_enabled)
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Opcional")

        self.hint = QLabel()
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)

        self.date_label = QLabel("Vencimento")
        self.end_row = QWidget()
        end_layout = QHBoxLayout(self.end_row)
        end_layout.setContentsMargins(0, 0, 0, 0)
        end_layout.addWidget(self.end_check)
        end_layout.addWidget(self.end_date_edit)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.addRow("Nome", self.name_edit)
        form.addRow("Valor", self.amount_edit)
        form.addRow(self.date_label, self.date_edit)
        form.addRow("Categoria", self.category_combo)
        form.addRow("Tipo", self.kind_combo)
        form.addRow("Frequência", self.frequency_combo)
        form.addRow("Término", self.end_row)
        form.addRow("Observações", self.notes_edit)

        self.delete_button = QPushButton("Excluir")
        self.delete_button.setObjectName("danger")
        self.delete_button.clicked.connect(self._delete)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Salvar")
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self._save)

        buttons = QHBoxLayout()
        buttons.addWidget(self.delete_button)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        title = QLabel(self.windowTitle())
        title.setObjectName("title")
        layout.addWidget(title)
        layout.addWidget(self.hint)
        layout.addLayout(form)
        layout.addSpacing(6)
        layout.addLayout(buttons)

        self.name_edit.setFocus()

    def _fill(self, default_kind: str) -> None:
        today = self.service.today()
        if self.mode == MODE_SERIES:
            s = self.series
            self.name_edit.setText(s.name)
            self.amount_edit.setText(f"{s.amount_cents / 100:.2f}".replace(".", ","))
            self.date_edit.setDate(_to_qdate(s.start_date))
            self.category_combo.setCurrentText(s.category)
            self.kind_combo.setCurrentIndex(self.kind_combo.findData(s.kind))
            self.frequency_combo.setCurrentIndex(self.frequency_combo.findData(s.frequency))
            self.notes_edit.setText(s.notes)
            if s.end_date:
                self.end_check.setChecked(True)
                self.end_date_edit.setDate(_to_qdate(s.end_date))
            self.hint.setText(
                "Altere o modelo da série. O valor, nome e categoria valem a partir do mês atual; "
                "contas já pagas não mudam."
            )
        elif self.expense is not None:
            e = self.expense
            self.name_edit.setText(e.name)
            self.amount_edit.setText(f"{e.amount_cents / 100:.2f}".replace(".", ","))
            self.date_edit.setDate(_to_qdate(e.due_date))
            self.category_combo.setCurrentText(e.category)
            self.kind_combo.setCurrentIndex(self.kind_combo.findData("unico"))
            self.notes_edit.setText(e.notes)
            if self.mode == MODE_OCCURRENCE:
                self.kind_combo.setCurrentIndex(self.kind_combo.findData(e.kind))
                self.frequency_combo.setCurrentIndex(self.frequency_combo.findData(e.frequency))
                self.hint.setText(
                    "Esta conta faz parte de uma série. Alterar o valor vale só para este mês."
                )
            else:
                self.hint.setText(
                    "Para transformar em fixa ou recorrente, escolha o Tipo abaixo e salve."
                )
        else:
            self.date_edit.setDate(_to_qdate(today))
            self.kind_combo.setCurrentIndex(self.kind_combo.findData(default_kind))
            self.frequency_combo.setCurrentIndex(self.frequency_combo.findData("mensal"))
            self.hint.setText(
                "Fixa = orçamento mensal (aluguel, internet). "
                "Recorrente = assinaturas e mensalidades."
            )
        self.end_date_edit.setDate(self.date_edit.date().addMonths(12))
        self.delete_button.setVisible(self.expense is not None or self.series is not None)

    def _update_enabled(self) -> None:
        kind = self.kind_combo.currentData()
        is_series_kind = kind in ("fixo", "recorrente")
        series_mode = self.mode == MODE_SERIES
        occurrence_mode = self.mode == MODE_OCCURRENCE

        self.date_edit.setEnabled(not series_mode and not occurrence_mode)
        self.kind_combo.setEnabled(not series_mode and not occurrence_mode)
        self.frequency_combo.setEnabled(is_series_kind and not series_mode and not occurrence_mode)
        self.date_label.setText("Início" if series_mode else "Vencimento")
        self.end_row.setVisible(series_mode or (is_series_kind and not occurrence_mode))
        self.end_date_edit.setEnabled(self.end_check.isChecked())

    # ----- ações ------------------------------------------------------------
    def _read_form(self) -> dict:
        name = self.name_edit.text()
        amount = parse_money(self.amount_edit.text())
        due = self.date_edit.date().toPython()
        category = self.category_combo.currentText().strip() or "Outros"
        end = self.end_date_edit.date().toPython() if self.end_check.isChecked() else None
        return {
            "name": name,
            "amount_cents": amount,
            "due": due,
            "category": category,
            "notes": self.notes_edit.text(),
            "kind": self.kind_combo.currentData(),
            "frequency": self.frequency_combo.currentData(),
            "end_date": end,
        }

    def _save(self) -> None:
        try:
            data = self._read_form()
            if not self._confirm_duplicate(data):
                return
            if self.mode == MODE_SERIES:
                self.service.update_series(
                    self.series.id, data["name"], data["amount_cents"], data["category"],
                    data["notes"], data["end_date"],
                )
            elif self.mode == MODE_OCCURRENCE:
                self.service.update_expense(
                    self.expense.id, data["name"], data["amount_cents"], data["due"],
                    data["category"], data["notes"],
                )
            elif self.expense is not None:
                self.service.update_expense(
                    self.expense.id, data["name"], data["amount_cents"], data["due"],
                    data["category"], data["notes"],
                )
                if data["kind"] != "unico":
                    self.service.convert_to_series(
                        self.expense.id, data["kind"], data["frequency"], data["end_date"]
                    )
            else:
                self.service.add_expense(
                    data["name"], data["amount_cents"], data["due"], data["category"],
                    data["notes"], kind=data["kind"], frequency=data["frequency"],
                    end_date=data["end_date"],
                )
        except ValidationError as exc:
            QMessageBox.warning(self, "Não foi possível salvar", str(exc))
            return
        except ValueError as exc:
            QMessageBox.warning(self, "Valor inválido", str(exc))
            return
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "Erro ao salvar", f"O banco de dados recusou a operação:\n{exc}")
            return
        self.accept()

    def _confirm_duplicate(self, data: dict) -> bool:
        if self.expense is not None or data["kind"] != "unico":
            return True
        duplicate = self.service.find_duplicate(data["name"], data["due"], data["amount_cents"])
        if duplicate is None:
            return True
        answer = QMessageBox.question(
            self,
            "Conta possivelmente duplicada",
            f"Já existe '{duplicate.name}' com o mesmo valor ({format_money(duplicate.amount_cents)}) "
            "nesta data.\n\nDeseja cadastrar mesmo assim?",
        )
        return answer == QMessageBox.StandardButton.Yes

    def _delete(self) -> None:
        if self.mode == MODE_SERIES:
            text = (
                f"Excluir a série '{self.series.name}'?\n\n"
                "As contas não pagas serão removidas. As já pagas continuam no histórico."
            )
        elif self.mode == MODE_OCCURRENCE:
            text = f"Excluir '{self.expense.name}' deste mês?\nEla não voltará automaticamente."
        else:
            text = f"Excluir '{self.expense.name}'?"
        answer = QMessageBox.question(self, "Confirmar exclusão", text)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            if self.mode == MODE_SERIES:
                self.service.delete_series(self.series.id)
            else:
                self.service.delete_expense(self.expense.id)
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "Erro ao excluir", str(exc))
            return
        self.deleted = True
        self.accept()


def open_expense_dialog(
    service: FinanceService,
    parent: Optional[QWidget] = None,
    expense: Optional[Expense] = None,
    series: Optional[Series] = None,
    default_kind: str = "unico",
) -> bool:
    """Abre o formulário. Retorna True se algo foi salvo ou excluído."""
    dialog = ExpenseDialog(service, parent, expense=expense, series=series, default_kind=default_kind)
    dialog.exec()
    return dialog.result() == QDialog.DialogCode.Accepted
