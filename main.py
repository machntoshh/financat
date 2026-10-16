"""Ponto de entrada do Financat."""

from __future__ import annotations

import logging
import sqlite3
import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from financas import db
from financas.services import FinanceService
from ui.icon import app_icon
from ui.main_window import MainWindow
from ui.theme import stylesheet


def _log_path() -> Path:
    return db.default_db_path().parent / "erros.log"


def _install_error_handling() -> None:
    logging.basicConfig(
        filename=str(_log_path()),
        level=logging.ERROR,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )

    def handle(exc_type, exc, tb):
        logging.error("Erro não tratado:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))
        QMessageBox.critical(
            None,
            "Erro inesperado",
            "Algo deu errado, mas seus dados continuam salvos.\n\n"
            f"Detalhes foram gravados em:\n{_log_path()}\n\n{exc}",
        )

    sys.excepthook = handle


def _set_taskbar_identity() -> None:
    """Sem isso, rodando com 'python main.py' a barra de tarefas mostra o ícone do Python."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Financat.App")


def main() -> int:
    _set_taskbar_identity()
    app = QApplication(sys.argv)
    app.setApplicationName("Financat")
    app.setWindowIcon(app_icon())
    app.setStyleSheet(stylesheet())
    _install_error_handling()

    try:
        conn = db.connect(db.default_db_path())
    except (OSError, sqlite3.Error) as exc:
        QMessageBox.critical(None, "Não foi possível abrir os dados", str(exc))
        return 1

    window = MainWindow(FinanceService(conn))
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
