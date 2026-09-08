"""Fixed, invented demo cases matching the three public demo notes.

The seeded records deliberately have no photo paths. Demo images live in
``photos/demo`` for the video and repository, while the photo API serves only
private uploads from ``photos/private``.
"""

from __future__ import annotations


# Keep removed seed ids here so re-seeding also clears them from older demo DBs.
DEMO_CASE_IDS = (
    "demo-ausflug",
    "demo-elternabend",
    "demo-schliesstag",
    "demo-arzt",
)

REPLY_AUSFLUG = (
    "Sehr geehrte Frau Huber,\n\n"
    "hiermit bestätige ich, dass Mateo am Ausflug am Freitag, den 11.09.2026, "
    "teilnimmt. Die Gummistiefel geben wir mit.\n\n"
    "Mit freundlichen Grüßen\n"
    "Lucía García\n"
)

REPLY_ELTERNABEND = (
    "Sehr geehrte Damen und Herren,\n\n"
    "hiermit bestätige ich meine Teilnahme am Elternabend am Donnerstag, den "
    "17.09.2026, um 18:30 Uhr.\n\n"
    "Mit freundlichen Grüßen\n"
    "Lucía García\n"
)


def seed_cases() -> list[dict]:
    """Return the same fixed story on every machine and every demo day."""
    return [
        {
            "id": "demo-ausflug",
            "title": "Outing to the zoo",
            "sender": "Fr. Huber",
            "sender_type": "kindergarten",
            "status": "open",
            "language": "en",
            "event_date": "2026-09-11",
            "papers": [
                {
                    "id": "demo-ausflug-p1",
                    "kind": "original",
                    "received_on": "2026-09-03",
                    "text": (
                        "Der Ausflug in den Tiergarten findet am Mittwoch, den 09.09.2026, statt. "
                        "Bitte geben Sie Ihrem Kind bis Montag, den 07.09.2026, 8,- Euro in einem "
                        "beschrifteten Kuvert mit. Bitte an Fr. Huber abgeben."
                    ),
                },
                {
                    "id": "demo-ausflug-p2",
                    "kind": "amendment",
                    "received_on": "2026-09-08",
                    "text": (
                        "Der Ausflug wurde auf Freitag, den 11.09.2026, verschoben. Bitte geben Sie "
                        "Gummistiefel mit. Rückmeldung bis morgen."
                    ),
                },
            ],
            "actions": [
                {
                    "id": "demo-ausflug-pay",
                    "paper_id": "demo-ausflug-p1",
                    "kind": "pay",
                    "action": "Send 8 € in cash in a labelled envelope",
                    "deadline_iso": "2026-09-07",
                    "amount": 8.0,
                    "confidence": 0.96,
                    "source_line": (
                        "Bitte geben Sie Ihrem Kind bis Montag, den 07.09.2026, 8,- Euro in einem "
                        "beschrifteten Kuvert mit."
                    ),
                },
                {
                    "id": "demo-ausflug-attend-original",
                    "paper_id": "demo-ausflug-p1",
                    "kind": "attend",
                    "action": "Outing on Wednesday",
                    "deadline_iso": "2026-09-09",
                    "confidence": 0.96,
                    "status": "superseded",
                    "superseded_by": "demo-ausflug-attend-amended",
                    "source_line": (
                        "Der Ausflug in den Tiergarten findet am Mittwoch, den 09.09.2026, statt."
                    ),
                },
                {
                    "id": "demo-ausflug-attend-amended",
                    "paper_id": "demo-ausflug-p2",
                    "kind": "attend",
                    "action": "Outing on Friday",
                    "deadline_iso": "2026-09-11",
                    "confidence": 0.96,
                    "source_line": (
                        "Der Ausflug wurde auf Freitag, den 11.09.2026, verschoben."
                    ),
                },
                {
                    "id": "demo-ausflug-boots",
                    "paper_id": "demo-ausflug-p2",
                    "kind": "bring",
                    "action": "Bring rain boots",
                    "deadline_iso": "2026-09-11",
                    "confidence": 0.96,
                    "source_line": "Bitte geben Sie Gummistiefel mit.",
                },
                {
                    "id": "demo-ausflug-reply",
                    "paper_id": "demo-ausflug-p2",
                    "kind": "reply",
                    "action": "Confirm attendance",
                    "deadline_iso": "2026-09-09",
                    "confidence": 0.96,
                    "source_line": "Rückmeldung bis morgen.",
                },
            ],
            "artifacts": [
                {"kind": "ics", "content": "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"},
                {"kind": "reply", "content": REPLY_AUSFLUG},
            ],
        },
        {
            "id": "demo-elternabend",
            "title": "Parents' evening",
            "sender": "Kindergarten Sonnenblume",
            "sender_type": "kindergarten",
            "status": "open",
            "language": "en",
            "event_date": "2026-09-17",
            "papers": [
                {
                    "id": "demo-elternabend-p1",
                    "kind": "original",
                    "received_on": "2026-09-04",
                    "text": (
                        "Am Donnerstag, den 17.09.2026, findet um 18:30 Uhr unser Elternabend statt. "
                        "Bitte geben Sie bis Samstag, den 12.09.2026, bekannt, ob Sie teilnehmen. "
                        "Am 24.09.2026 ist der Kindergarten wegen Fortbildung geschlossen."
                    ),
                }
            ],
            "actions": [
                {
                    "id": "demo-elternabend-attend",
                    "paper_id": "demo-elternabend-p1",
                    "kind": "attend",
                    "action": "Parents' evening at 18:30",
                    "deadline_iso": "2026-09-17",
                    "confidence": 0.96,
                    "source_line": (
                        "Am Donnerstag, den 17.09.2026, findet um 18:30 Uhr unser Elternabend statt."
                    ),
                },
                {
                    "id": "demo-elternabend-reply",
                    "paper_id": "demo-elternabend-p1",
                    "kind": "reply",
                    "action": "Confirm attendance at the parents' evening",
                    "deadline_iso": "2026-09-12",
                    "confidence": 0.96,
                    "source_line": (
                        "Bitte geben Sie bis Samstag, den 12.09.2026, bekannt, ob Sie teilnehmen."
                    ),
                },
                {
                    "id": "demo-elternabend-closed",
                    "paper_id": "demo-elternabend-p1",
                    "kind": "closed",
                    "action": "Kindergarten closed for staff training",
                    "deadline_iso": "2026-09-24",
                    "confidence": 0.96,
                    "source_line": (
                        "Am 24.09.2026 ist der Kindergarten wegen Fortbildung geschlossen."
                    ),
                },
            ],
            "artifacts": [
                {"kind": "ics", "content": "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"},
                {"kind": "reply", "content": REPLY_ELTERNABEND},
            ],
        },
    ]
