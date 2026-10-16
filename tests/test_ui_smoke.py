"""Teste de fumaça da interface (offscreen): fluxo de pagamento e mascote."""

import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from financas import db  # noqa: E402
from financas.services import FinanceService  # noqa: E402
from ui import mascot as mascot_module  # noqa: E402
from ui.dashboard import ExpenseRow  # noqa: E402
from ui.expense_dialog import ExpenseDialog  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.theme import stylesheet  # noqa: E402

APP = QApplication.instance() or QApplication([])
APP.setStyleSheet(stylesheet())


class MainWindowSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self.tmp.name) / "ui.db")
        self.today = date(2026, 10, 15)
        self.svc = FinanceService(self.conn, today=lambda: self.today,
                                  now=lambda: datetime(2026, 10, 15, 10, 0))
        self.svc.add_expense("Luz", 15000, date(2026, 10, 20), "Contas da casa")
        self.svc.add_expense("Academia", 9900, date(2026, 10, 5), kind="fixo")
        self.window = MainWindow(self.svc)
        self.window.mascot._animate = False  # sem timers de animação nos testes

    def tearDown(self):
        self.window.close()
        self.conn.close()
        self.tmp.cleanup()

    def _rows(self):
        return self.window.dashboard.findChildren(ExpenseRow)

    def test_dashboard_lists_month(self):
        names = {row.expense.name for row in self._rows()}
        self.assertEqual(names, {"Luz", "Academia"})
        self.assertEqual(self.window.dashboard.stat_total.value.text(), "R$ 249,00")

    def test_paying_celebrates_once_and_persists(self):
        count = []
        self.window.dashboard.payment_made.connect(lambda: count.append(1))
        luz = next(r.expense for r in self._rows() if r.expense.name == "Luz")
        self.window.dashboard._toggle_paid(luz.id, True)
        self.assertEqual(len(count), 1)
        self.assertEqual(self.window.mascot.state, mascot_module.HAPPY)
        self.assertTrue(self.svc.get_expense(luz.id).is_paid)

        self.window.dashboard._toggle_paid(luz.id, False)  # desfazer: sem nova comemoração
        self.assertEqual(len(count), 1)
        self.assertFalse(self.svc.get_expense(luz.id).is_paid)

    def test_pages_refresh_and_filters_work(self):
        dash = self.window.dashboard
        dash._set_filter("fixos")
        self.assertEqual([r.expense.name for r in self._rows()], ["Academia"])
        dash._set_filter("todas")
        dash._move_month(1)
        self.assertEqual(dash.title.text(), "Novembro de 2026")
        self.assertEqual(self._rows()[0].expense.name, "Academia")  # fixo gerado em novembro

    def test_bills_and_series_pages_render(self):
        self.window.bills.refresh()
        self.assertEqual(self.window.bills.table.rowCount(), 1)  # só a avulsa
        self.assertEqual(self.window.fixed.table.rowCount(), 1)
        self.assertEqual(self.window.recurring.table.rowCount(), 0)

    def test_dialogs_open_in_each_mode(self):
        luz = self.svc.unique_expenses()[0]
        academia = next(e for e in self.svc.month_summary(2026, 10).items if e.series_id)
        series = self.svc.list_series("fixo")[0]
        for kwargs in (
            {},
            {"expense": luz},
            {"expense": academia},
            {"series": series},
        ):
            dialog = ExpenseDialog(self.svc, **kwargs)
            dialog.close()

    def test_dialog_creates_and_converts(self):
        dialog = ExpenseDialog(self.svc)
        dialog.name_edit.setText("Plano de saúde")
        dialog.amount_edit.setText("350,00")
        dialog.kind_combo.setCurrentIndex(dialog.kind_combo.findData("recorrente"))
        dialog._save()
        self.assertEqual(dialog.result(), 1)
        series = self.svc.list_series("recorrente")
        self.assertEqual([s.name for s in series], ["Plano de saúde"])
        self.assertEqual(series[0].amount_cents, 35000)

        luz = next(e for e in self.svc.unique_expenses() if e.name == "Luz")
        dialog = ExpenseDialog(self.svc, expense=luz)
        dialog.kind_combo.setCurrentIndex(dialog.kind_combo.findData("fixo"))
        dialog._save()
        self.assertEqual(dialog.result(), 1)
        self.assertEqual(len(self.svc.list_series("fixo")), 2)  # Academia + Luz convertida

    def test_mascot_states(self):
        mascot = self.window.mascot
        self.assertEqual(mascot.state, mascot_module.IDLE)
        mascot.celebrate()
        self.assertEqual(mascot.state, mascot_module.HAPPY)
        mascot.celebrate()  # repetido reinicia, não empilha
        self.assertEqual(mascot.state, mascot_module.HAPPY)
        mascot.grab()  # força pintura sem erros


if __name__ == "__main__":
    unittest.main()


class AppIconTests(unittest.TestCase):
    def test_app_icon_comes_from_sprite(self):
        from ui.icon import app_icon

        icon = app_icon()
        self.assertFalse(icon.isNull())
        self.assertIn(16, [s.width() for s in icon.availableSizes()])
