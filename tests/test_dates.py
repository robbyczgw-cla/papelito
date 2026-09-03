"""Tests for the deterministic German/Austrian date parser."""

import unittest

from papelito.dates import DateResolution, resolve_dates

RECEIVED = "2026-09-03"  # Thursday


def iso(phrase: str, received_on: str = RECEIVED) -> str | None:
    return resolve_dates(phrase, received_on).iso


class TestExplicitDates(unittest.TestCase):
    def test_german_dotted_with_year(self):
        self.assertEqual(iso("Freitag, 12.09.2026"), "2026-09-12")
        self.assertEqual(iso("am Mittwoch, 17.09.2026"), "2026-09-17")
        self.assertEqual(iso("17. 9. 2026"), "2026-09-17")
        self.assertEqual(iso("12.9.2026"), "2026-09-12")
        self.assertEqual(iso("12.09.26"), "2026-09-12")

    def test_iso_date(self):
        self.assertEqual(iso("2026-09-12"), "2026-09-12")

    def test_month_name_austrian(self):
        self.assertEqual(iso("1. Oktober 2026"), "2026-10-01")
        self.assertEqual(iso("1. Jänner 2027"), "2027-01-01")
        self.assertEqual(iso("12. Sept. 2026"), "2026-09-12")
        self.assertEqual(iso("am 24. September 2026"), "2026-09-24")

    def test_prefixes_bis_zum_and_spaetestens(self):
        self.assertEqual(iso("bis zum 24.09.2026"), "2026-09-24")
        self.assertEqual(iso("spätestens am 12.09.2026"), "2026-09-12")
        self.assertEqual(iso("spätestens bis zum 17.09.2026"), "2026-09-17")

    def test_calendar_date_wins_over_wrong_weekday(self):
        # 12.09.2026 is a Saturday; the note still names Freitag.
        self.assertEqual(iso("bis Freitag, 12.09.2026"), "2026-09-12")
        # 17.09.2026 is a Thursday; the note still names Mittwoch.
        self.assertEqual(iso("am Mittwoch, 17.09.2026"), "2026-09-17")

    def test_ignores_clock_time(self):
        phrase = "am Mittwoch, 17.09.2026 findet um 18:30 Uhr"
        self.assertEqual(iso(phrase), "2026-09-17")
        self.assertEqual(iso("Elternabend am 17.09.2026, 18.30 Uhr"), "2026-09-17")

    def test_range_takes_the_bis_end(self):
        self.assertEqual(
            iso("von 15.09.2026 bis 19.09.2026"), "2026-09-19"
        )


class TestRelativeWeekday(unittest.TestCase):
    def test_bis_freitag_after_thursday(self):
        self.assertEqual(iso("bis Freitag", RECEIVED), "2026-09-04")

    def test_bis_zum_and_spaetestens_weekday(self):
        self.assertEqual(iso("bis zum Freitag", RECEIVED), "2026-09-04")
        self.assertEqual(iso("spätestens Freitag", RECEIVED), "2026-09-04")
        self.assertEqual(iso("spätestens am Freitag", RECEIVED), "2026-09-04")

    def test_bare_weekday(self):
        self.assertEqual(iso("Freitag", RECEIVED), "2026-09-04")
        self.assertEqual(iso("am Montag", RECEIVED), "2026-09-07")

    def test_same_weekday_as_received_on_is_that_day(self):
        self.assertEqual(iso("bis Freitag", "2026-09-04"), "2026-09-04")

    def test_naechsten_weekday_skips_today(self):
        self.assertEqual(iso("nächsten Freitag", "2026-09-04"), "2026-09-11")
        self.assertEqual(iso("nächsten Freitag", RECEIVED), "2026-09-04")

    def test_von_montag_bis_freitag_takes_end(self):
        self.assertEqual(iso("von Montag bis Freitag", RECEIVED), "2026-09-04")


class TestRelativeDuration(unittest.TestCase):
    def test_innerhalb_von_14_tagen(self):
        self.assertEqual(iso("innerhalb von 14 Tagen", RECEIVED), "2026-09-17")

    def test_variants(self):
        self.assertEqual(iso("binnen 14 Tagen", RECEIVED), "2026-09-17")
        self.assertEqual(iso("in 14 Tagen", RECEIVED), "2026-09-17")
        self.assertEqual(iso("in den nächsten 14 Tagen", RECEIVED), "2026-09-17")
        self.assertEqual(iso("innerhalb von 2 Wochen", RECEIVED), "2026-09-17")
        self.assertEqual(iso("innerhalb von zwei Wochen", RECEIVED), "2026-09-17")
        self.assertEqual(iso("innerhalb von vierzehn Tagen", RECEIVED), "2026-09-17")

    def test_one_week(self):
        self.assertEqual(iso("innerhalb von einer Woche", RECEIVED), "2026-09-10")


class TestMonthOnlyYearFromReceived(unittest.TestCase):
    def test_trailing_dot(self):
        self.assertEqual(iso("Am 24.09.", RECEIVED), "2026-09-24")
        self.assertEqual(iso("24.09.", RECEIVED), "2026-09-24")

    def test_bare_day_month(self):
        self.assertEqual(iso("24.09", RECEIVED), "2026-09-24")
        self.assertEqual(iso("24.9.", RECEIVED), "2026-09-24")
        self.assertEqual(iso("bis zum 24.09.", RECEIVED), "2026-09-24")

    def test_year_comes_from_received_on_even_across_new_year(self):
        self.assertEqual(iso("Am 24.09.", "2027-01-10"), "2027-09-24")

    def test_month_name_without_year(self):
        self.assertEqual(iso("am 1. Oktober", RECEIVED), "2026-10-01")


class TestAmbiguousDoesNotInvent(unittest.TestCase):
    def test_empty_and_blank(self):
        self.assertIsNone(iso(""))
        self.assertIsNone(iso("   "))
        self.assertEqual(resolve_dates("", RECEIVED).miss, "empty_phrase")

    def test_no_date_phrase(self):
        for phrase in (
            "bald",
            "so bald wie möglich",
            "nächste Woche",
            "im September",
            "Ende der Woche",
            "siehe Aushang",
            "Fr. Huber",
            "Frau Huber",
            "KW 38",
            "ab sofort",
        ):
            with self.subTest(phrase=phrase):
                result = resolve_dates(phrase, RECEIVED)
                self.assertIsNone(result.iso, msg=phrase)
                self.assertIsNotNone(result.miss, msg=phrase)

    def test_frau_abbreviation_is_not_friday(self):
        result = resolve_dates("bitte bei Fr. Huber abgeben", RECEIVED)
        self.assertIsNone(result.iso)
        self.assertEqual(result.miss, "no_date")

    def test_choice_of_two_dates(self):
        result = resolve_dates("12.09.2026 oder 13.09.2026", RECEIVED)
        self.assertIsNone(result.iso)
        self.assertEqual(result.miss, "ambiguous")

    def test_recurring_weekday(self):
        result = resolve_dates("jeden Freitag", RECEIVED)
        self.assertIsNone(result.iso)
        self.assertEqual(result.miss, "ambiguous")

    def test_invalid_calendar_date(self):
        result = resolve_dates("31.02.2026", RECEIVED)
        self.assertIsNone(result.iso)
        self.assertEqual(result.miss, "invalid_calendar_date")
        self.assertIsNone(iso("32.09.2026"))

    def test_invalid_received_on(self):
        result = resolve_dates("bis Freitag", "03.09.2026")
        self.assertIsNone(result.iso)
        self.assertEqual(result.miss, "invalid_received_on")

    def test_slash_date_is_not_guessed(self):
        result = resolve_dates("12/09/2026", RECEIVED)
        self.assertIsNone(result.iso)

    def test_miss_has_zero_confidence(self):
        result = resolve_dates("bald", RECEIVED)
        self.assertEqual(result.confidence, 0.0)
        self.assertFalse(result)


class TestGoldenNotePhrases(unittest.TestCase):
    def test_synthetic_kindergarten_note_lines(self):
        self.assertEqual(
            iso("am Mittwoch, 17.09.2026 findet um 18:30 Uhr unser Elternabend statt."),
            "2026-09-17",
        )
        self.assertEqual(
            iso("Bitte geben Sie bis Freitag, 12.09.2026 bekannt"),
            "2026-09-12",
        )
        self.assertEqual(
            iso("Am 24.09. ist der Kindergarten wegen Fortbildung geschlossen."),
            "2026-09-24",
        )


class TestResolutionShape(unittest.TestCase):
    def test_hit_is_structured(self):
        result = resolve_dates("bis Freitag", RECEIVED)
        self.assertIsInstance(result, DateResolution)
        self.assertEqual(result.iso, "2026-09-04")
        self.assertIsNone(result.miss)
        self.assertGreater(result.confidence, 0.0)
        self.assertTrue(result)
        self.assertEqual(str(result)[:10], "2026-09-04")


if __name__ == "__main__":
    unittest.main()
