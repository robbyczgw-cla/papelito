"""Gate 3: fake today, one English reminder, then silence after mark_replied."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from papelito.watch import compose_reminder, mark_done, read_last_run, run_watch


class MemoryStore:
    """Duck-typed store: list_open, mark_due, mark_replied, list_due, close_case."""

    def __init__(self, cases=None):
        self.cases = {c["id"]: dict(c) for c in (cases or [])}
        self.events = []

    def list_open(self):
        out = []
        for case in self.cases.values():
            status = str(case.get("status") or "open").lower()
            if status in {"replied", "closed", "done"}:
                continue
            if case.get("replied") or case.get("replied_at"):
                continue
            out.append(case)
        return out

    def list_due(self):
        return [c for c in self.list_open() if str(c.get("status") or "").lower() == "due"]

    def mark_due(self, case_id, reminder_text):
        case = self.cases[case_id]
        case["status"] = "due"
        case["due_line"] = reminder_text
        case["reminder"] = reminder_text

    def mark_replied(self, case_id):
        case = self.cases[case_id]
        case["status"] = "replied"
        case["replied_at"] = "2026-09-10T08:00:00+00:00"
        case["due_line"] = None
        return True

    def close_case(self, case_id, detail=None):
        case = self.cases[case_id]
        case["status"] = "closed"
        case["asked_sent"] = True
        if detail:
            case["due_line"] = detail

    def log_event(self, case_id, kind, detail=None):
        self.events.append({"case_id": case_id, "kind": kind, "detail": detail})


def _gate3_store():
    return MemoryStore(
        [
            {
                "id": "ausflug",
                "title": "Ausflug",
                "sender": "Fr. Huber",
                "language": "en",
                "status": "open",
                "actions": [
                    {
                        "action": "8 Euro bar mitgeben",
                        "deadline_iso": "2026-09-12",
                        "amount": 8,
                        "status": "active",
                        "source_line": "bitte 8 Euro bar bis Montag mitgeben",
                    }
                ],
            },
            {
                "id": "elternabend",
                "title": "Elternabend",
                "language": "en",
                "status": "open",
                "actions": [
                    {
                        "action": "kommen",
                        "deadline_iso": "2026-10-01",
                        "status": "active",
                        "source_line": "Elternabend am 1. Oktober",
                    }
                ],
            },
        ]
    )


class WatchTests(unittest.TestCase):
    def setUp(self):
        self._env = {k: os.environ.pop(k) for k in list(os.environ) if k.startswith("TELEGRAM_") or k.startswith("SMTP") or k.startswith("PAPELITO_SMTP") or k.startswith("PAPELITO_MAIL")}
        self._watch_log = tempfile.NamedTemporaryFile(prefix="papelito-watch-", suffix=".json", delete=False)
        self._watch_log.close()
        os.environ["PAPELITO_WATCH_LOG"] = self._watch_log.name

    def tearDown(self):
        os.environ.pop("PAPELITO_WATCH_LOG", None)
        Path(self._watch_log.name).unlink(missing_ok=True)
        os.environ.update(self._env)

    def test_gate3_fake_today_one_english_reminder(self):
        store = _gate3_store()
        report = run_watch(store, today=date(2026, 9, 10), language="English", notify=False)

        self.assertEqual(len(report.reminders), 1)
        self.assertEqual(len(report.texts), 1)
        reminder = report.reminders[0]
        self.assertEqual(reminder.case_id, "ausflug")
        self.assertEqual(reminder.kind, "due")
        self.assertEqual(
            reminder.text,
            "In two days: 8 € for the Ausflug, cash, Fr. Huber.",
        )
        self.assertEqual(store.cases["ausflug"]["status"], "due")
        self.assertEqual(store.cases["ausflug"]["due_line"], reminder.text)
        self.assertEqual(store.cases["elternabend"]["status"], "open")
        self.assertEqual([c["id"] for c in store.list_due()], ["ausflug"])
        tools = [e["tool"] for e in report.traces]
        self.assertIn("list_open", tools)
        self.assertIn("list_due", tools)
        self.assertIn("mark_due", tools)
        last = read_last_run()
        self.assertIsNotNone(last)
        self.assertEqual(last["today"], "2026-09-10")
        self.assertEqual(len(last["nagged"]), 1)
        self.assertEqual(last["nagged"][0]["case_id"], "ausflug")

    def test_after_mark_replied_next_run_is_noop(self):
        store = _gate3_store()
        initial_report = run_watch(store, today="2026-09-10", language="English", notify=False)
        self.assertEqual(len(initial_report.reminders), 1)

        self.assertTrue(mark_done("ausflug", store=store))
        self.assertEqual(store.cases["ausflug"]["status"], "replied")

        second = run_watch(store, today=date(2026, 9, 10), language="English", notify=False)
        self.assertEqual(second.reminders, [])
        self.assertEqual(second.texts, [])
        self.assertEqual(store.cases["elternabend"]["status"], "open")

    def test_after_deadline_asks_once_then_closes(self):
        store = _gate3_store()
        report = run_watch(store, today=date(2026, 9, 13), language="English", notify=False)
        self.assertEqual(len(report.reminders), 1)
        self.assertEqual(report.reminders[0].kind, "ask_sent")
        self.assertEqual(report.reminders[0].text, "Did you send the reply?")
        self.assertEqual(store.cases["ausflug"]["status"], "closed")

        again = run_watch(store, today=date(2026, 9, 14), language="English", notify=False)
        self.assertEqual(again.reminders, [])

    def test_compose_tomorrow_is_english(self):
        case = {
            "id": "ausflug",
            "title": "Ausflug",
            "sender": "Fr. Huber",
            "language": "English",
            "deadline": "2026-09-11",
            "amount": 8,
        }
        text = compose_reminder(case, date(2026, 9, 10), "English")
        self.assertEqual(text, "Tomorrow: 8 € for the Ausflug, cash, Fr. Huber.")


class RealStoreWatchTests(unittest.TestCase):
    def test_gate3_against_papelito_store(self):
        try:
            from papelito.store import Store
        except ImportError:
            self.skipTest("papelito.store not present")
        db = Store(":memory:")
        db.save_case(
            {
                "id": "ausflug",
                "title": "Ausflug",
                "sender": "Fr. Huber",
                "language": "en",
                "actions": [
                    {
                        "kind": "pay",
                        "action": "8 Euro bar mitgeben",
                        "deadline_iso": "2026-09-12",
                        "amount": 8,
                        "source_line": "bitte 8 Euro bar bis Montag mitgeben",
                        "confidence": 1.0,
                    }
                ],
            }
        )
        report = run_watch(db, today=date(2026, 9, 10), language="English", notify=False)
        self.assertEqual(len(report.texts), 1)
        self.assertIn("In two days", report.texts[0])
        self.assertEqual(db.get_case("ausflug")["status"], "due")

        self.assertTrue(mark_done("ausflug", store=db))
        silent = run_watch(db, today=date(2026, 9, 10), language="English", notify=False)
        self.assertEqual(silent.texts, [])
        db.close()


if __name__ == "__main__":
    unittest.main()
