"""Tests for papelito.ics.write_ics."""

from __future__ import annotations

import re
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from papelito.ics import TZID, event_uid, write_ics

SAMPLE = {
    "id": "case-elternabend-1",
    "title": "Elternabend",
    "one_liner": "Tomorrow: confirm attendance at the Elternabend.",
    "actions": [
        {
            "action": "RSVP",
            "deadline_iso": "2026-09-12",
            "amount": None,
            "source_line": "Bitte geben Sie bis Freitag, 12.09.2026 bekannt",
            "all_day": True,
        },
        {
            "action": "Elternabend",
            "deadline_iso": "2026-09-17T18:30:00",
            "amount": None,
            "source_line": "am Mittwoch, 17.09.2026 findet um 18:30 Uhr",
        },
    ],
}

NOW = datetime(2026, 9, 3, 12, 0, 0)


def unfold(ics: str) -> list[str]:
    lines: list[str] = []
    for line in ics.split("\r\n"):
        if line.startswith(" ") and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def components(ics: str, name: str) -> list[list[str]]:
    found: list[list[str]] = []
    current: list[str] | None = None
    for line in unfold(ics):
        if line == f"BEGIN:{name}":
            current = [line]
        elif current is not None:
            current.append(line)
            if line == f"END:{name}":
                found.append(current)
                current = None
    return found


def prop(lines: list[str], name: str) -> str | None:
    prefix = name if name.endswith(":") or ";" in name else f"{name}"
    for line in lines:
        if line == prefix or line.startswith(prefix + ":") or line.startswith(prefix + ";"):
            return line.split(":", 1)[1] if ":" in line else ""
        if line.startswith(name + ":") or line.startswith(name + ";"):
            return line.split(":", 1)[1]
    return None


class WriteIcsTests(unittest.TestCase):
    def test_rfc5545_envelope(self):
        ics = write_ics(SAMPLE, now=NOW)
        self.assertTrue(ics.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(ics.endswith("END:VCALENDAR\r\n"))
        self.assertNotRegex(ics, r"[^\r]\n")
        lines = unfold(ics)
        for required in (
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Papelito//Papelito 0.1//DE",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VTIMEZONE",
            f"TZID:{TZID}",
            "BEGIN:DAYLIGHT",
            "BEGIN:STANDARD",
            "END:VTIMEZONE",
            "END:VCALENDAR",
        ):
            self.assertIn(required, lines)
        self.assertEqual(lines.count("BEGIN:VEVENT"), 2)
        self.assertEqual(lines.count("END:VEVENT"), 2)
        self.assertEqual(lines.count("BEGIN:VALARM"), 2)
        self.assertLess(ics.index("BEGIN:VTIMEZONE"), ics.index("BEGIN:VEVENT"))

    def test_each_event_has_uid_and_dtstamp(self):
        ics = write_ics(SAMPLE, now=NOW)
        for event in components(ics, "VEVENT"):
            self.assertIsNotNone(prop(event, "UID"))
            self.assertEqual(prop(event, "DTSTAMP"), "20260903T120000Z")
            self.assertTrue(any(line.startswith("UID:") for line in event))
            self.assertTrue(any(line.startswith("DTSTAMP:") for line in event))

    def test_all_day_uses_value_date(self):
        ics = write_ics(SAMPLE, now=NOW)
        rsvp = components(ics, "VEVENT")[0]
        self.assertIn("DTSTART;VALUE=DATE:20260912", rsvp)
        self.assertIn("DTEND;VALUE=DATE:20260913", rsvp)
        self.assertFalse(any("DTSTART;TZID=" in line for line in rsvp))

    def test_all_day_year_boundary(self):
        case = {
            "id": "nye",
            "title": "Schultag",
            "actions": [
                {"action": "Schultag", "deadline_iso": "2026-12-31", "all_day": True}
            ],
        }
        ics = write_ics(case, now=NOW)
        self.assertIn("DTSTART;VALUE=DATE:20261231", ics)
        self.assertIn("DTEND;VALUE=DATE:20270101", ics)

    def test_timed_event_is_vienna_local(self):
        ics = write_ics(SAMPLE, now=NOW)
        event = components(ics, "VEVENT")[1]
        self.assertIn(f"DTSTART;TZID={TZID}:20260917T183000", event)
        self.assertIn(f"DTEND;TZID={TZID}:20260917T193000", event)
        self.assertNotIn("20260917T163000", ics)

    def test_naive_iso_stays_wall_clock_in_winter(self):
        case = {
            "id": "winter",
            "title": "Elternabend",
            "actions": [{"action": "Elternabend", "deadline_iso": "2026-01-15T18:30:00"}],
        }
        ics = write_ics(case, now=NOW)
        self.assertIn(f"DTSTART;TZID={TZID}:20260115T183000", unfold(ics))

    def test_utc_deadline_converts_to_vienna(self):
        case = {
            "id": "utc",
            "title": "Elternabend",
            "actions": [{"action": "Elternabend", "deadline_iso": "2026-09-17T16:30:00Z"}],
        }
        ics = write_ics(case, now=NOW)
        self.assertIn(f"DTSTART;TZID={TZID}:20260917T183000", unfold(ics))

    def test_valarm_trigger_is_48_hours(self):
        ics = write_ics(SAMPLE, now=NOW)
        alarms = components(ics, "VALARM")
        self.assertEqual(len(alarms), 2)
        allowed = {"-P2D", "-PT48H"}
        for alarm in alarms:
            self.assertIn("ACTION:DISPLAY", alarm)
            trigger = prop(alarm, "TRIGGER")
            self.assertIsNotNone(trigger)
            self.assertIn(trigger, allowed)
            self.assertTrue(re.fullmatch(r"-P2D|-PT48H", trigger or ""))
        rsvp_alarm = components(ics, "VEVENT")[0]
        alarm_lines = rsvp_alarm[rsvp_alarm.index("BEGIN:VALARM") :]
        self.assertEqual(prop(alarm_lines, "TRIGGER"), "-P2D")
        timed_alarm = components(ics, "VEVENT")[1]
        alarm_lines = timed_alarm[timed_alarm.index("BEGIN:VALARM") :]
        self.assertEqual(prop(alarm_lines, "TRIGGER"), "-PT48H")

    def test_uids_are_stable_across_amendment(self):
        original = write_ics(SAMPLE, now=NOW)
        amended_case = {
            **SAMPLE,
            "sequence": 1,
            "actions": [
                {**SAMPLE["actions"][0], "deadline_iso": "2026-09-11"},
                {**SAMPLE["actions"][1], "deadline_iso": "2026-09-18T18:00:00"},
            ],
        }
        amended = write_ics(amended_case, now=NOW)
        original_uids = [prop(event, "UID") for event in components(original, "VEVENT")]
        amended_uids = [prop(event, "UID") for event in components(amended, "VEVENT")]
        self.assertEqual(original_uids, amended_uids)
        self.assertEqual(
            original_uids,
            [
                event_uid("case-elternabend-1", "RSVP"),
                event_uid("case-elternabend-1", "Elternabend"),
            ],
        )
        self.assertIn("DTSTART;VALUE=DATE:20260911", amended)
        self.assertIn(f"DTSTART;TZID={TZID}:20260918T180000", amended)
        self.assertEqual(prop(components(amended, "VEVENT")[0], "SEQUENCE"), "1")

    @patch("papelito.ics.UID_HOST", "example.invalid")
    def test_duplicate_action_names_get_distinct_stable_uids(self):
        case = {
            "id": "dup",
            "title": "Ausflug",
            "actions": [
                {"action": "RSVP", "deadline_iso": "2026-09-10", "all_day": True},
                {"action": "RSVP", "deadline_iso": "2026-09-12", "all_day": True},
            ],
        }
        first = [prop(e, "UID") for e in components(write_ics(case, now=NOW), "VEVENT")]
        second = [prop(e, "UID") for e in components(write_ics(case, now=NOW), "VEVENT")]
        self.assertEqual(first, second)
        self.assertEqual(len(set(first)), 2)
        self.assertTrue(first[1].endswith("-2@example.invalid"))

    def test_summary_is_german_institution_language(self):
        ics = write_ics(SAMPLE, now=NOW)
        events = components(ics, "VEVENT")
        self.assertEqual(prop(events[0], "SUMMARY"), "RSVP: Elternabend")
        self.assertEqual(prop(events[1], "SUMMARY"), "Elternabend")

    def test_description_includes_reader_line_and_source_line(self):
        ics = write_ics(SAMPLE, now=NOW)
        rsvp = unfold(ics)
        desc = next(line for line in rsvp if line.startswith("DESCRIPTION:"))
        self.assertIn("Tomorrow: confirm attendance at the Elternabend.", desc)
        self.assertIn("Bitte geben Sie bis Freitag\\, 12.09.2026 bekannt", desc)

    def test_amount_lands_in_description(self):
        case = {
            "id": "ausflug",
            "title": "Ausflug",
            "actions": [
                {
                    "action": "Beitrag",
                    "deadline_iso": "2026-09-08",
                    "all_day": True,
                    "amount": 8,
                    "source_line": "bitte 8 Euro in bar mitgeben",
                }
            ],
        }
        ics = write_ics(case, now=NOW)
        desc = next(line for line in unfold(ics) if line.startswith("DESCRIPTION:"))
        self.assertIn("8 €", desc)

    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "elternabend.ics"
            text = write_ics(SAMPLE, path, now=NOW)
            self.assertTrue(path.is_file())
            on_disk = path.read_bytes()
            self.assertEqual(on_disk, text.encode("utf-8"))
            parsed = on_disk.decode("utf-8")
            self.assertIn("BEGIN:VEVENT", parsed)
            self.assertIn("TRIGGER:-P2D", parsed)
            self.assertIn("TRIGGER:-PT48H", parsed)

    def test_accepts_dataclass(self):
        @dataclass
        class Action:
            action: str
            deadline_iso: str
            amount: float | None = None
            source_line: str | None = None
            all_day: bool | None = None

        @dataclass
        class Case:
            id: str
            title: str
            actions: list
            one_liner: str | None = None

        case = Case(
            id="dc-1",
            title="Elternabend",
            one_liner="Confirm attendance.",
            actions=[
                Action(
                    action="RSVP",
                    deadline_iso="2026-09-12",
                    all_day=True,
                    source_line="bis Freitag",
                )
            ],
        )
        ics = write_ics(case, now=NOW)
        self.assertIn("BEGIN:VEVENT", ics)
        self.assertIn("DTSTART;VALUE=DATE:20260912", ics)
        self.assertIn("Confirm attendance.", ics)

    def test_accepts_json_string(self):
        import json

        ics = write_ics(json.dumps(SAMPLE), now=NOW)
        self.assertEqual(len(components(ics, "VEVENT")), 2)

    def test_long_line_is_folded_at_75_octets(self):
        long_en = "Yes. " * 80
        case = {
            "id": "fold",
            "title": "Elternabend",
            "one_liner": long_en,
            "actions": [
                {
                    "action": "RSVP",
                    "deadline_iso": "2026-09-12",
                    "all_day": True,
                    "source_line": "Bitte geben Sie bis Freitag, 12.09.2026 bekannt",
                }
            ],
        }
        ics = write_ics(case, now=NOW)
        for physical in ics.split("\r\n"):
            if physical == "":
                continue
            self.assertLessEqual(len(physical.encode("utf-8")), 75, physical)

    def test_skips_action_without_deadline(self):
        case = {
            "id": "skip",
            "title": "Hinweis",
            "actions": [
                {"action": "Lesen", "deadline_iso": None, "source_line": "nur zur Info"},
                {"action": "RSVP", "deadline_iso": "2026-09-12", "all_day": True},
            ],
        }
        ics = write_ics(case, now=NOW)
        self.assertEqual(len(components(ics, "VEVENT")), 1)

    @patch("papelito.ics.UID_HOST", "example.invalid")
    def test_uid_contains_case_and_action(self):
        uid = event_uid("case-elternabend-1", "RSVP")
        self.assertEqual(uid, "case-elternabend-1-rsvp@example.invalid")
        self.assertIn("elternabend", event_uid("abc", "Elternabend"))


if __name__ == "__main__":
    unittest.main()
