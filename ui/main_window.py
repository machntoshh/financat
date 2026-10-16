"""Janela principal: barra lateral com mascote e navegação + área de conteúdo."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from financas.db import default_db_path
from financas.services import FinanceService, ValidationError

from .bills_page import BillsPage
from .common import confirm
from .dashboard import DashboardPage
from .expense_dialog import open_expense_dialog
from .mascot import CatMascot
from .series_page import SeriesPage

TOAST_MS = 2600


class MainWindow(QMainWindow):
    def __init__(self, service: FinanceService):
        super().__init__()
        self.service = service
        self.setWindowTitle("Financat")
        self.resize(1180, 760)
        self.setMinimumSize(980, 620)

        self.mascot = CatMascot()

        self.dashboard = DashboardPage(service)
        self.bills = BillsPage(service)
        self.fixed = SeriesPage(service, "fixo")
        self.recurring = SeriesPage(service, "recorrente")
        self.pages = [self.dashboard, self.bills, self.fixed, self.recurring]

        self.stack = QStackedWidget()
        for page in self.pages:
            self.stack.addWidget(page)
            page.data_changed.connect(self._on_data_changed)
            page.payment_made.connect(self.mascot.celebrate)

        self.toast = QLabel("")
        self.toast.setObjectName("toast")
        self.toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast.hide()
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self.toast.hide)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.stack, 1)
        toast_row = QHBoxLayout()
        toast_row.addStretch()
        toast_row.addWidget(self.toast)
        toast_row.addStretch()
        toast_row.setContentsMargins(0, 0, 0, 14)
        content_layout.addLayout(toast_row)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_sidebar())
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)

        self.stack.setCurrentWidget(self.dashboard)

    # ----- barra lateral ----------------------------------------------------
    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(232)

        brand = QLabel("Finanças")
        brand.setObjectName("section")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)

        nav_items = [
            ("Mês", self.dashboard),
            ("Contas a pagar", self.bills),
            ("Gastos fixos", self.fixed),
            ("Gastos recorrentes", self.recurring),
        ]
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(6)
        layout.addWidget(self.mascot, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(brand)
        layout.addSpacing(8)
        for index, (label, page) in enumerate(nav_items):
            button = QPushButton(label)
            button.setObjectName("nav")
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.clicked.connect(lambda _c=False, p=page: self.stack.setCurrentWidget(p))
            self.nav_group.addButton(button)
            layout.addWidget(button)

        layout.addStretch()
        add_btn = QPushButton("+ Adicionar conta")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._add_account)
        layout.addWidget(add_btn)
        layout.addSpacing(10)
        for label, handler in (
            ("Exportar CSV", self._export_csv),
            ("Fazer backup", self._backup),
            ("Restaurar backup", self._restore),
        ):
            button = QPushButton(label)
            button.setObjectName("ghost")
            button.clicked.connect(handler)
            layout.addWidget(button)
        return sidebar

    # ----- ações globais ----------------------------------------------------
    def _add_account(self) -> None:
        if open_expense_dialog(self.service, self):
            self._on_data_changed("Conta adicionada")

    def _on_data_changed(self, message: str) -> None:
        for page in self.pages:
            page.refresh()
        if message:
            self._show_toast(message)

    def _show_toast(self, message: str) -> None:
        self.toast.setText(f"✓  {message}" if message else "")
        self.toast.adjustSize()
        self.toast.show()
        self._toast_timer.start(TOAST_MS)

    def _export_csv(self) -> None:
        default = f"financas_{datetime.now():%Y%m%d}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar para CSV", default, "CSV (*.csv)")
        if not path:
            return
        try:
            count = self.service.export_csv(path)
        except (OSError, sqlite3.Error) as exc:
            QMessageBox.critical(self, "Erro ao exportar", f"Não foi possível gravar o arquivo:\n{exc}")
            return
        self._show_toast(f"{count} conta(s) exportada(s)")

    def _backup(self) -> None:
        default = f"backup_financas_{datetime.now():%Y%m%d_%H%M}.db"
        path, _ = QFileDialog.getSaveFileName(self, "Salvar backup", default, "Backup (*.db)")
        if not path:
            return
        try:
            self.service.backup(path)
        except (OSError, sqlite3.Error) as exc:
            QMessageBox.critical(self, "Erro no backup", f"Não foi possível salvar o backup:\n{exc}")
            return
        self._show_toast("Backup salvo")

    def _restore(self) -> None:
        if not confirm(
            self,
            "Restaurar backup",
            "Os dados atuais serão substituídos pelos do backup.\n\n"
            "Antes disso, uma cópia de segurança dos dados atuais será salva na pasta do aplicativo.\n\n"
            "Continuar?",
        ):
            return
        path, _ = QFileDialog.getOpenFileName(self, "Escolher backup", "", "Backup (*.db)")
        if not path:
            return
        safety = default_db_path().parent / f"antes_da_restauracao_{datetime.now():%Y%m%d_%H%M%S}.db"
        try:
            self.service.restore(path, safety_copy=str(safety))
        except (ValidationError, ValueError) as exc:
            QMessageBox.warning(self, "Backup inválido", str(exc))
            return
        except (OSError, sqlite3.Error) as exc:
            QMessageBox.critical(self, "Erro ao restaurar", str(exc))
            return
        self._on_data_changed("Backup restaurado")
