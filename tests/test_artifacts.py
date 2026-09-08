"""Calendar downloads must preserve the confidence gate."""

import unittest
from unittest.mock import patch

from web.artifacts import ics_for


class CalendarConfidenceTests(unittest.TestCase):
    def row(self, **overrides):
        return {"status": "active", "gate": "ok", "deadline": "2026-09-12",
                "do": "Confirm attendance", "what": "Parents' evening", **overrides}

    def test_pending_or_rejected_rows_are_not_exported(self):
        case = {"id": "uncertain", "rows": [
            self.row(status="pending"), self.row(gate="ask"),
            self.row(gate="drop"), self.row(status="superseded"),
        ]}
        self.assertNotIn("BEGIN:VEVENT", ics_for(case))

    def test_empty_core_calendar_does_not_fall_back_to_unconfirmed_rows(self):
        case = {"id": "uncertain", "_raw": {"id": "uncertain", "actions": []},
                "rows": [self.row()]}
        with patch("papelito.ics.write_ics", return_value="BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"):
            self.assertNotIn("BEGIN:VEVENT", ics_for(case))

    def test_confirmed_fallback_row_retains_alarm(self):
        calendar = ics_for({"id": "confirmed", "rows": [self.row()]})
        self.assertEqual(calendar.count("BEGIN:VEVENT"), 1)
        self.assertIn("TRIGGER:-PT48H", calendar)
