"""The two things the human taps: the German reply, and the calendar file.

Both delegate to the core modules when they exist. The fallbacks here are
stubs so the page stays tappable; they never send anything.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from web.store import parse_date


def reply_for(case: dict) -> str:
    """German draft. Never sent, only copied by the human."""
    if case.get("reply_de"):
        return str(case["reply_de"])
    if case.get("_raw"):
        try:
            from papelito.reply import draft_reply  # type: ignore

            text = draft_reply(case["_raw"])
            if text:
                return str(text)
        except Exception:
            pass
    return (
        "Sehr geehrte Damen und Herren,\n\n"
        "[Der Antworttext wird noch erstellt.]\n\n"
        "Mit freundlichen Grüßen\n"
    )


def _fold(line: str) -> str:
    """iCalendar lines wrap at 75 octets."""
    out, current = [], line
    while len(current.encode()) > 75:
        cut = 74
        while len(current[:cut].encode()) > 74:
            cut -= 1
        out.append(current[:cut])
        current = " " + current[cut:]
    out.append(current)
    return "\r\n".join(out)


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,").replace("\n", r"\n")


def ics_for(case: dict) -> str:
    """VEVENT per case with a VALARM 48 h before. Core write_ics wins if present."""
    if case.get("_raw"):
        try:
            from papelito.ics import write_ics  # type: ignore

            text = write_ics(case["_raw"])
            if text and "BEGIN:VEVENT" in str(text):
                return str(text)
        except Exception:
            pass

    stamp = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Papelito//web//EN",
        "CALSCALE:GREGORIAN",
    ]
    rows = [r for r in case.get("rows", []) if r["status"] != "superseded"]
    for n, row in enumerate(rows, start=1):
        day = parse_date(row.get("deadline"))
        if not day:
            continue
        title = row["do"] or row["what"] or case.get("what") or "Papelito"
        body = [f"Papelito: {case.get('what') or ''}", f"What to do: {row['do']}"]
        if row.get("amount"):
            body.append(f"Amount: {row['amount']}")
        if row.get("source_line"):
            body.append(f"Original: {row['source_line']}")
        lines += [
            "BEGIN:VEVENT",
            f"UID:papelito-{case.get('id')}-{n}@papelito",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
            f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
            _fold(f"SUMMARY:{_escape(str(title))}"),
            _fold(f"DESCRIPTION:{_escape(chr(10).join(body))}"),
            "BEGIN:VALARM",
            "TRIGGER:-PT48H",
            "ACTION:DISPLAY",
            _fold(f"DESCRIPTION:{_escape(str(title))}"),
            "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
