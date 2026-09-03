"""Demo cases, so the page can be looked at before a real photo is read.

Invented Kindergarten paper in the shape ``papelito.store`` keeps: a case with
papers, actions and artifacts. The card wording comes from ``papelito.explain``
in the UI language, exactly as it does for a real note. Titles are the German
event names the extractor keeps. No real names.

The Ausflug case carries two papers: the original note and a follow-up that
moved the day and added rain boots. That is the amendment the page must show.
"""

from __future__ import annotations

from datetime import timedelta

from web.store import today


def _d(offset: int) -> str:
    return (today() + timedelta(days=offset)).isoformat()


REPLY_AUSFLUG = (
    "Sehr geehrte Frau Huber,\n\n"
    "danke für die Information zum Ausflug am Freitag. Der Betrag von 8,- Euro wird am "
    "Montag in einem beschrifteten Kuvert mitgegeben, die Regenstiefel ebenso.\n\n"
    "Mit freundlichen Grüßen\n"
)

REPLY_ELTERNABEND = (
    "Sehr geehrte Damen und Herren,\n\n"
    "hiermit bestätige ich die Teilnahme am Elternabend.\n\n"
    "Mit freundlichen Grüßen\n"
)


def seed_cases() -> list[dict]:
    return [
        {
            "id": "demo-ausflug",
            "title": "Ausflug in den Tiergarten",
            "sender": "Fr. Huber",
            "sender_type": "kindergarten",
            "status": "due",
            "language": "en",
            "event_date": _d(2),
            "due_line": "Tomorrow: 8 € for the Ausflug, cash, Fr. Huber.",
            "papers": [
                {
                    "id": "demo-ausflug-p1",
                    "kind": "original",
                    "received_on": _d(-6),
                    "text": "Der Ausflug in den Tiergarten findet am Mittwoch statt. Bitte geben Sie "
                            "Ihrem Kind bis Montag 8,- Euro in einem beschrifteten Kuvert mit.",
                },
                {
                    "id": "demo-ausflug-p2",
                    "kind": "amendment",
                    "received_on": _d(-2),
                    "text": "Der Ausflug wurde auf Freitag verschoben. Regenstiefel nicht vergessen.",
                },
            ],
            "actions": [
                {
                    "id": "demo-ausflug-a1", "paper_id": "demo-ausflug-p1", "kind": "pay", "action": "8 € mitgeben",
                    "deadline_iso": _d(1), "amount": 8.0, "confidence": 0.94,
                    "source_line": "Bitte geben Sie Ihrem Kind bis Montag 8,- Euro in "
                                   "einem beschrifteten Kuvert mit.",
                },
                {
                    "id": "demo-ausflug-a3", "paper_id": "demo-ausflug-p1", "kind": "attend",
                    "action": "Ausflug am Mittwoch", "deadline_iso": _d(-1), "confidence": 0.9,
                    "status": "superseded", "superseded_by": "demo-ausflug-a4",
                    "source_line": "Der Ausflug in den Tiergarten findet am Mittwoch statt.",
                },
                {
                    "id": "demo-ausflug-a4", "paper_id": "demo-ausflug-p2", "kind": "attend",
                    "action": "Ausflug am Freitag", "deadline_iso": _d(2), "confidence": 0.92,
                    "source_line": "Der Ausflug wurde auf Freitag verschoben.",
                },
                {
                    "id": "demo-ausflug-a2", "paper_id": "demo-ausflug-p2", "kind": "bring", "action": "Regenstiefel",
                    "deadline_iso": _d(2), "confidence": 0.9,
                    "source_line": "Regenstiefel nicht vergessen.",
                },
            ],
            "artifacts": [
                {"kind": "ics", "content": "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"},
                {"kind": "reply", "content": REPLY_AUSFLUG},
            ],
        },
        {
            "id": "demo-elternabend",
            "title": "Elternabend",
            "sender": "Kindergarten Sonnenblume",
            "status": "open",
            "language": "en",
            "papers": [{
                "id": "demo-elternabend-p1",
                "received_on": _d(-9),
                "text": "Einladung zum Elternabend. Rückmeldung bitte bis Freitag.",
            }],
            "actions": [{
                "id": "demo-elternabend-a1", "kind": "reply", "action": "Rückmeldung abgeben",
                "deadline_iso": _d(-1), "confidence": 0.91,
                "source_line": "Rückmeldung bitte bis Freitag.",
            }],
            "artifacts": [
                {"kind": "ics", "content": "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"},
                {"kind": "reply", "content": REPLY_ELTERNABEND},
            ],
        },
        {
            "id": "demo-schliesstag",
            "title": "Schließtag",
            "sender": "Kindergarten",
            "status": "open",
            "language": "en",
            "papers": [{
                "id": "demo-schliesstag-p1",
                "received_on": _d(-1),
                "text": "Am Do. 18. bleibt der Kindergarten geschlossen.",
            }],
            "actions": [{
                "id": "demo-schliesstag-a1", "kind": "closed", "action": "Kindergarten geschlossen",
                "deadline_iso": _d(11), "confidence": 0.42,
                "source_line": "Am Do. 18. bleibt der Kindergarten geschlossen.",
            }],
        },
        {
            "id": "demo-arzt",
            "title": "Jährliche Kontrolluntersuchung",
            "sender": "Arztpraxis",
            "sender_type": "arzt",
            "status": "replied",
            "language": "en",
            "papers": [{
                "id": "demo-arzt-p1",
                "received_on": _d(-20),
                "text": "Bitte bringen Sie das unterschriebene Formular mit.",
            }],
            "actions": [{
                "id": "demo-arzt-a1", "kind": "bring", "action": "unterschriebenes Formular",
                "deadline_iso": _d(-6), "confidence": 0.88,
                "source_line": "Bitte bringen Sie das unterschriebene Formular mit.",
            }],
            "artifacts": [{"kind": "reply", "content": REPLY_ELTERNABEND}],
        },
    ]
