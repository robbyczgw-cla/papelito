"""PII strip and query builder for lookup_office. No live network."""

from __future__ import annotations

import os
import unittest

from papelito.lookup import build_office_query, lookup_office_contact, strip_pii

PROFILE_BLOB = """
names:
  parent: "Lucía García"
  household: "Demo household"
child: "Mateo"
kindergarten: "Kindergarten Sonnenblume"
address_line: "Demo Street 12, 00000 Demo City"
phone: "+43 1 234 56 78"
email: "lucia.garcia@example.invalid"
reader_language: "English"
reply_signature: "Lucía García"
"""


class TestStripPii(unittest.TestCase):
    def test_profile_blob_drops_email_phone_address_and_given_names(self) -> None:
        cleaned = strip_pii(PROFILE_BLOB)
        lowered = cleaned.lower()
        for needle in (
            "lucia.garcia@example.invalid",
            "lucía",
            "lucia",
            "mateo",
            "garcía",
            "garcia",
            "familia",
            "beispielgasse",
            "+43",
            "234 56 78",
            "example.com",
        ):
            self.assertNotIn(needle, lowered, f"still present: {needle!r}\n{cleaned}")
        self.assertIn("Sonnenblume", cleaned)

    def test_loose_blob_same_fields(self) -> None:
        blob = (
            "parent Lucía García child Mateo "
            "email reply@example.invalid phone +00 000 0000 "
            "address Hauptstraße 5, 4020 Linz "
            "kindergarten Kindergarten Sonnenblume"
        )
        cleaned = strip_pii(blob)
        lowered = cleaned.lower()
        self.assertNotIn("reply@example.invalid", lowered)
        self.assertNotIn("0664", cleaned)
        self.assertNotIn("Hauptstraße", cleaned)
        self.assertNotIn("Hauptstrasse", cleaned)
        self.assertNotIn("mateo", lowered)
        self.assertIn("Sonnenblume", cleaned)


class TestQueryBuilder(unittest.TestCase):
    def test_keeps_kindergarten_name(self) -> None:
        self.assertEqual(
            build_office_query("Kindergarten Sonnenblume"),
            "Kindergarten Sonnenblume Wien Kontakt",
        )

    def test_bare_name_gets_kindergarten_prefix(self) -> None:
        self.assertEqual(
            build_office_query("Sonnenblume"),
            "Kindergarten Sonnenblume Wien Kontakt",
        )

    def test_profile_blob_keeps_office_drops_pii(self) -> None:
        query = build_office_query(PROFILE_BLOB)
        self.assertEqual(query, "Kindergarten Sonnenblume Wien Kontakt")
        self.assertNotIn("Mateo", query)
        self.assertNotIn("Demo Street", query)
        self.assertNotIn("lucia.garcia", query.lower())

    def test_gemeinde_shape(self) -> None:
        self.assertEqual(
            build_office_query("Gemeinde Donaustadt"),
            "Gemeinde Donaustadt Amt Telefon",
        )

    def test_ma_shape(self) -> None:
        self.assertEqual(build_office_query("MA 11"), "MA 11 Wien Amt Telefon")


class TestLookupStub(unittest.TestCase):
    def test_stub_search_uses_stripped_query(self) -> None:
        previous = os.environ.get("PAPELITO_LOOKUP_STUB")
        os.environ["PAPELITO_LOOKUP_STUB"] = "1"
        try:
            result = lookup_office_contact(PROFILE_BLOB)
        finally:
            if previous is None:
                os.environ.pop("PAPELITO_LOOKUP_STUB", None)
            else:
                os.environ["PAPELITO_LOOKUP_STUB"] = previous
        self.assertTrue(result["stub"])
        self.assertEqual(result["query"], "Kindergarten Sonnenblume Wien Kontakt")
        self.assertIsNone(result["phone"])


if __name__ == "__main__":
    unittest.main()
