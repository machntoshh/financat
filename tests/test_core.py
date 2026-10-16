"""Testes do núcleo financeiro (sem interface gráfica)."""

import csv
import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from financas import db
from financas.formatting import due_label, format_money, parse_money
from financas.recurrence import due_dates_between
from financas.services import FinanceService, ValidationError, apply_filter


class Clock:
    def __init__(self, day):
        self.day = day

    def __call__(self):
        return self.day


class RecurrenceTests(unittest.TestCase):
    def test_monthly_clips_to_last_day(self):
        dates = due_dates_between(date(2026, 1, 31), "mensal", date(2026, 1, 1), date(2026, 4, 30))
        self.assertEqual(dates, [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)])

    def test_weekly_starts_on_series_start(self):
        dates = due_dates_between(date(2026, 10, 1), "semanal", date(2026, 10, 10), date(2026, 10, 31))
        self.assertEqual(dates, [date(2026, 10, 15), date(2026, 10, 22), date(2026, 10, 29)])

    def test_annual_only_in_start_month(self):
        dates = due_dates_between(date(2024, 3, 10), "anual", date(2024, 1, 1), date(2026, 12, 31))
        self.assertEqual(dates, [date(2024, 3, 10), date(2025, 3, 10), date(2026, 3, 10)])

    def test_nothing_before_start(self):
        self.assertEqual(due_dates_between(date(2026, 5, 5), "mensal", date(2026, 1, 1), date(2026, 4, 30)), [])


class FormattingTests(unittest.TestCase):
    def test_parse_money_brazilian_and_dot_formats(self):
        self.assertEqual(parse_money("1.234,56"), 123456)
        self.assertEqual(parse_money("R$ 90"), 9000)
        self.assertEqual(parse_money("12.5"), 1250)

    def test_parse_money_rejects_invalid(self):
        for bad in ("", "abc", "-5"):
            with self.assertRaises(ValueError):
                parse_money(bad)

    def test_format_money(self):
        self.assertEqual(format_money(123456), "R$ 1.234,56")

    def test_due_label(self):
        today = date(2026, 10, 15)
        self.assertEqual(due_label(today, today), "Vence hoje")
        self.assertEqual(due_label(date(2026, 10, 16), today), "Vence amanhã")
        self.assertEqual(due_label(date(2026, 10, 20), today), "Vence em 5 dias")
        self.assertEqual(due_label(date(2026, 10, 14), today), "Venceu há 1 dia")


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "teste.db"
        self.conn = db.connect(self.db_path)
        self.clock = Clock(date(2026, 10, 15))
        self.svc = FinanceService(self.conn, today=self.clock, now=lambda: datetime(2026, 10, 15, 9, 30))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_add_and_validate(self):
        self.svc.add_expense("Luz", 15000, date(2026, 10, 20), "Contas da casa")
        summary = self.svc.month_summary(2026, 10)
        self.assertEqual(len(summary.items), 1)
        self.assertEqual(summary.total_cents, 15000)
        with self.assertRaises(ValidationError):
            self.svc.add_expense("  ", 100, date(2026, 10, 20))
        with self.assertRaises(ValidationError):
            self.svc.add_expense("Zero", 0, date(2026, 10, 20))

    def test_status_overdue_and_paid(self):
        self.svc.add_expense("Água", 5000, date(2026, 10, 10))
        exp = self.svc.month_summary(2026, 10).items[0]
        self.assertEqual(exp.status(self.clock.day), "vencido")
        self.assertTrue(self.svc.set_paid(exp.id, True))
        self.assertEqual(self.svc.get_expense(exp.id).status(self.clock.day), "pago")
        summary = self.svc.month_summary(2026, 10)
        self.assertEqual((summary.paid_cents, summary.pending_cents), (5000, 0))

    def test_celebrate_only_on_real_transition(self):
        self.svc.add_expense("Net", 5990, date(2026, 10, 25))
        exp_id = self.svc.month_summary(2026, 10).items[0].id
        self.assertTrue(self.svc.set_paid(exp_id, True))
        self.assertFalse(self.svc.set_paid(exp_id, True))   # já paga
        self.assertFalse(self.svc.set_paid(exp_id, False))  # desfazer não comemora

    def test_recurring_no_duplicates_and_skip_on_delete(self):
        self.svc.add_expense("Academia", 9900, date(2026, 10, 5), kind="fixo", frequency="mensal")
        self.svc.ensure_month(2026, 10)
        self.svc.ensure_month(2026, 10)
        summary = self.svc.month_summary(2026, 10)
        self.assertEqual(len(summary.items), 1)
        self.assertEqual(summary.items[0].series_kind, "fixo")
        self.svc.delete_expense(summary.items[0].id)
        self.assertEqual(self.svc.month_summary(2026, 10).items, [])

    def test_override_only_affects_one_month(self):
        self.svc.add_expense("Internet", 10000, date(2026, 10, 10), kind="fixo")
        oct_item = self.svc.month_summary(2026, 10).items[0]
        self.svc.update_expense(oct_item.id, "Internet", 12000, oct_item.due_date, "Outros", "")
        nov = self.svc.month_summary(2026, 11).items[0]
        self.assertEqual(nov.amount_cents, 10000)
        self.assertEqual(self.svc.month_summary(2026, 10).items[0].amount_cents, 12000)

    def test_series_template_change_keeps_overrides_and_paid(self):
        self.svc.add_expense("Aluguel", 100000, date(2026, 10, 5), kind="fixo")
        items = self.svc.month_summary(2026, 10).items
        series_id = items[0].series_id
        self.svc.set_paid(items[0].id, True)
        self.svc.month_summary(2026, 11)  # gera novembro
        self.svc.update_expense(self.svc.month_summary(2026, 11).items[0].id,
                                "Aluguel", 90000, date(2026, 11, 5), "Outros", "")
        series = self.svc.get_series(series_id)
        self.svc.update_series(series_id, "Aluguel", 120000, "Moradia", "", None)
        self.assertEqual(self.svc.month_summary(2026, 10).items[0].amount_cents, 100000)  # paga, intacta
        self.assertEqual(self.svc.month_summary(2026, 11).items[0].amount_cents, 90000)  # override mantido
        self.assertEqual(self.svc.month_summary(2026, 12).items[0].amount_cents, 120000)  # futuro novo
        self.assertEqual(series.amount_cents, 100000)

    def test_end_date_stops_generation(self):
        self.svc.add_expense("Curso", 20000, date(2026, 10, 3), kind="recorrente", frequency="mensal")
        sid = self.svc.list_series("recorrente")[0].id
        self.svc.update_series(sid, "Curso", 20000, "Outros", "", date(2026, 11, 30))
        self.assertEqual(len(self.svc.month_summary(2026, 11).items), 1)
        self.assertEqual(self.svc.month_summary(2026, 12).items, [])

    def test_convert_one_off_keeps_payment(self):
        self.svc.add_expense("Seguro", 30000, date(2026, 10, 12))
        exp = self.svc.month_summary(2026, 10).items[0]
        self.svc.set_paid(exp.id, True)
        self.svc.convert_to_series(exp.id, "recorrente", "mensal")
        summary = self.svc.month_summary(2026, 10)
        self.assertEqual(len(summary.items), 1)
        self.assertTrue(summary.items[0].is_paid)
        self.assertEqual(summary.items[0].series_kind, "recorrente")
        self.assertEqual(len(self.svc.month_summary(2026, 11).items), 1)

    def test_delete_series_keeps_paid_history(self):
        self.svc.add_expense("Streaming", 3990, date(2026, 10, 1), kind="recorrente")
        first = self.svc.month_summary(2026, 10).items[0]
        self.svc.set_paid(first.id, True)
        self.svc.month_summary(2026, 11)
        self.svc.delete_series(first.series_id)
        self.assertEqual([e.name for e in self.svc.month_summary(2026, 10).items], ["Streaming"])
        self.assertEqual(self.svc.month_summary(2026, 11).items, [])

    def test_filters(self):
        self.svc.add_expense("A", 100, date(2026, 10, 1))
        self.svc.add_expense("B", 100, date(2026, 10, 30))
        items = self.svc.month_summary(2026, 10).items
        self.svc.set_paid(items[1].id, True)
        items = self.svc.month_summary(2026, 10).items
        self.assertEqual([e.name for e in apply_filter(items, "vencidas", self.clock.day)], ["A"])
        self.assertEqual([e.name for e in apply_filter(items, "pagas", self.clock.day)], ["B"])
        self.assertEqual(apply_filter(items, "fixos", self.clock.day), [])

    def test_duplicate_detection(self):
        self.svc.add_expense("Gás", 8000, date(2026, 10, 9))
        self.assertIsNotNone(self.svc.find_duplicate("gás ", date(2026, 10, 9), 8000))
        self.assertIsNone(self.svc.find_duplicate("Gás", date(2026, 10, 10), 8000))

    def test_backup_restore_and_csv(self):
        self.svc.add_expense("Mercado", 45050, date(2026, 10, 7), "Alimentação", "semana 1")
        backup_path = Path(self.tmp.name) / "backup.db"
        self.svc.backup(str(backup_path))
        self.svc.add_expense("Outra", 100, date(2026, 10, 8))
        self.svc.restore(str(backup_path), safety_copy=str(Path(self.tmp.name) / "seguranca.db"))
        names = [e.name for e in self.svc.month_summary(2026, 10).items]
        self.assertEqual(names, ["Mercado"])

        csv_path = Path(self.tmp.name) / "dados.csv"
        self.assertEqual(self.svc.export_csv(str(csv_path)), 1)
        with open(csv_path, encoding="utf-8-sig") as handle:
            rows = list(csv.reader(handle, delimiter=";"))
        self.assertEqual(rows[1][1], "Mercado")
        self.assertEqual(rows[1][5], "450,50")
        self.assertEqual(len(rows), 2)  # cabeçalho + 1 conta

    def test_csv_includes_scheduled_occurrences(self):
        self.svc.add_expense("Internet", 10000, date(2026, 10, 10), kind="fixo")
        csv_path = Path(self.tmp.name) / "fixas.csv"
        count = self.svc.export_csv(str(csv_path))
        self.assertEqual(count, 13)  # de out/2026 (início da série) até out/2027

    def test_restore_rejects_foreign_file(self):
        bogus = Path(self.tmp.name) / "outro.db"
        other = sqlite3.connect(bogus)
        other.execute("CREATE TABLE x (a)")
        other.commit()
        other.close()
        with self.assertRaises(ValueError):
            self.svc.restore(str(bogus))
        with self.assertRaises(ValueError):
            self.svc.restore(str(Path(self.tmp.name) / "inexistente.db"))

    def test_data_persists_after_reopen(self):
        self.svc.add_expense("Persistente", 1000, date(2026, 10, 2))
        self.conn.close()
        self.conn = db.connect(self.db_path)
        svc = FinanceService(self.conn, today=self.clock)
        self.assertEqual([e.name for e in svc.month_summary(2026, 10).items], ["Persistente"])


if __name__ == "__main__":
    unittest.main()
