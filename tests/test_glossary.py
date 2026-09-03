"""Tests for the static Austrian glossary."""

from __future__ import annotations

import unittest

from papelito.glossary import glossary_at, list_terms

REQUIRED = (
    "Kindergarten",
    "Kita",
    "MA",
    "Gemeinde",
    "Hort",
    "Elternverein",
    "Meldezettel",
    "Elternabend",
    "Ausflug",
    "Rückmeldung",
    "Fortbildung",
    "Schließtage",
    "Beitrag",
    "Hortanmeldung",
    "Kindergartenpflicht",
    "Kindergartenbeitrag",
    "Jausen",
    "Regenkleidung",
    "Einverständniserklärung",
    "Abholberechtigung",
)


def _blob(hit: dict) -> str:
    cites = " ".join(
        f"{c.get('name', '')} {c.get('url', '')}" for c in hit.get("citations") or []
    )
    return " ".join(
        [
            hit.get("term") or "",
            hit.get("en") or "",
            hit.get("explanation") or "",
            " ".join(hit.get("see_also") or []),
            cites,
        ]
    )


class GlossaryTests(unittest.TestCase):
    def test_required_terms_are_present(self) -> None:
        names = set(list_terms())
        missing = [term for term in REQUIRED if term not in names]
        self.assertEqual(missing, [], f"missing required terms: {missing}")

    def test_each_required_lookup_has_english_gloss_and_explanation(self) -> None:
        for term in REQUIRED:
            with self.subTest(term=term):
                hit = glossary_at(term)
                self.assertTrue(hit["found"], term)
                self.assertEqual(hit["term"], term)
                self.assertTrue(hit["en"], f"{term} needs an English gloss")
                self.assertTrue(hit["explanation"], f"{term} needs an explanation")
                self.assertGreaterEqual(len(hit["en"].split()), 4)

    def test_kita_is_not_the_austrian_kindergarten_word(self) -> None:
        hit = glossary_at("Kita")
        self.assertTrue(hit["found"])
        self.assertEqual(hit["term"], "Kita")
        text = _blob(hit).lower()
        self.assertIn("wrong", text)
        self.assertTrue(
            "not the austrian" in text
            or "wrong german word" in text
            or "not kita" in text
        )
        self.assertIn("germany", text)
        self.assertIn("kindergarten", text)
        self.assertIn("austria", hit["en"].lower())
        self.assertIn("Kindergarten", hit.get("see_also", []))

    def test_kita_aliases_and_case(self) -> None:
        for query in ("kita", "KITA", "KiTa", "Kindertagesstätte"):
            hit = glossary_at(query)
            self.assertEqual(hit["term"], "Kita", query)
            self.assertIn("wrong", hit["explanation"].lower())

    def test_kindergarten_is_the_austrian_word(self) -> None:
        hit = glossary_at("Kindergarten")
        text = _blob(hit).lower()
        self.assertIn("austria", text)
        self.assertIn("kita", text)
        self.assertNotIn("finanzamt", text)

    def test_ma_is_vienna_magistrat_not_gemeindeamt(self) -> None:
        ma = glossary_at("MA")
        gemeinde = glossary_at("Gemeinde")
        self.assertTrue(ma["found"] and gemeinde["found"])
        self.assertEqual(ma["term"], "MA")
        self.assertEqual(gemeinde["term"], "Gemeinde")
        ma_text = _blob(ma).lower()
        ge_text = _blob(gemeinde).lower()
        self.assertIn("magistrat", ma_text)
        self.assertIn("magistratsabteilung", ma_text)
        self.assertIn("vienna", ma_text)
        self.assertIn("ma 10", ma_text)
        self.assertIn("gemeindeamt", ge_text)
        self.assertIn("municipality", ge_text)
        self.assertIn("not", ma_text)
        self.assertTrue(
            "gemeindeamt" in ma_text or "not a village" in ma_text,
            ma["explanation"],
        )
        self.assertNotEqual(ma["explanation"], gemeinde["explanation"])
        self.assertIn("Gemeinde", ma.get("see_also", []))
        self.assertIn("MA", gemeinde.get("see_also", []))

    def test_ma10_and_magistrat_resolve_to_ma(self) -> None:
        for query in ("MA 10", "MA10", "Magistrat", "Magistratsabteilung"):
            hit = glossary_at(query)
            self.assertEqual(hit["term"], "MA", query)

    def test_umlauts_and_misspellings(self) -> None:
        cases = {
            "Rueckmeldung": "Rückmeldung",
            "ruckmeldung": "Rückmeldung",
            "Schliesstage": "Schließtage",
            "schliestage": "Schließtage",
            "Kindergarden": "Kindergarten",
            "kindergaten": "Kindergarten",
            "Gummistiefel": "Regenkleidung",
            "jause": "Jausen",
            "Einverstaendniserklaerung": "Einverständniserklärung",
            "Hort-Anmeldung": "Hortanmeldung",
            "Elterenabend": "Elternabend",
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                hit = glossary_at(query)
                self.assertTrue(hit["found"], query)
                self.assertEqual(hit["term"], expected, query)

    def test_cited_entries_have_source_name_and_url(self) -> None:
        for term in REQUIRED:
            hit = glossary_at(term)
            if term == "Rückmeldung":
                self.assertIn("unverified", hit["explanation"].lower())
                continue
            self.assertTrue(hit["citations"], f"{term} needs citations")
            for cite in hit["citations"]:
                self.assertTrue(cite.get("name"), term)
                self.assertTrue(
                    str(cite.get("url", "")).startswith("http"),
                    f"{term} citation URL: {cite}",
                )

    def test_unknown_term_is_unverified(self) -> None:
        hit = glossary_at("unknown-office-appeal")
        self.assertFalse(hit["found"])
        self.assertIn("unverified", hit["explanation"].lower())

    def test_empty_term_is_unverified(self) -> None:
        hit = glossary_at("   ")
        self.assertFalse(hit["found"])
        self.assertIn("unverified", hit["explanation"].lower())

    def test_no_competitor_word_in_product_copy(self) -> None:
        forbidden = "zettel"
        for term in list_terms():
            hit = glossary_at(term)
            for field in ("en", "explanation"):
                text = hit.get(field) or ""
                lowered = text.lower()
                if forbidden not in lowered:
                    continue
                remainder = lowered.replace("meldezettel", "")
                self.assertNotIn(
                    forbidden,
                    remainder,
                    f"{term}.{field} contains competitor word: {text}",
                )

    def test_hort_is_not_kindergarten(self) -> None:
        hit = glossary_at("Hort")
        text = hit["explanation"].lower()
        self.assertIn("school", text)
        self.assertIn("not kindergarten", text)

    def test_kindergartenpflicht_is_cited_duty_not_guessed(self) -> None:
        hit = glossary_at("Kindergartenpflicht")
        text = _blob(hit).lower()
        self.assertIn("20 hours", text)
        self.assertTrue("31 august" in text or "2 september" in text)
        urls = [c["url"] for c in hit["citations"]]
        self.assertTrue(any("ris.bka.gv.at" in url for url in urls))

    def test_meldezettel_is_the_austrian_document_name(self) -> None:
        hit = glossary_at("Meldezettel")
        text = _blob(hit).lower()
        self.assertIn("meldezettel", text)
        self.assertIn("zentrales melderegister", text)
        self.assertIn("oesterreich.gv.at", " ".join(c["url"] for c in hit["citations"]))


if __name__ == "__main__":
    unittest.main()
