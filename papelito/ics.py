"""RFC 5545 calendar export: one VEVENT per action, VALARM 48 hours before.

Timed events are local Europe/Vienna with a VTIMEZONE block so Apple Calendar
and Google Calendar both import the file. All-day deadlines use VALUE=DATE.
UIDs are stable per (case id, action) so an amendment replaces the event.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

TZID = "Europe/Vienna"
VIENNA = ZoneInfo(TZID)
PRODID = "-//Papelito//Papelito 0.1//DE"
UID_HOST = "papelito.local"
ALARM_TRIGGER_ALL_DAY = "-P2D"
ALARM_TRIGGER_TIMED = "-PT48H"
CRLF = "\r\n"
_MAX_LINE_OCTETS = 75

_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_READER_LINE_KEYS = (
    "one_liner",
    "oneliner",
    "english",
    "explanation",
    "explain",
)


def write_ics(
    case: Any,
    path: str | Path | None = None,
    *,
    now: datetime | None = None,
) -> str:
    """Build a METHOD:PUBLISH calendar for a case and optionally write it.

    ``case`` is a dict or dataclass with ``id``, ``title`` and ``actions``.
    Returns the ICS text (CRLF, UTF-8). When ``path`` is set, also writes
    that file so it can be opened in Google Calendar or Apple Calendar.
    """
    case = _as_mapping(case)
    stamp = _utc_stamp(now)
    actions = list(_get(case, "actions") or [])
    title = str(_get(case, "title") or "Papelito")
    case_id = str(_get(case, "id") or "case")
    sequence = _int(_get(case, "sequence"), default=0)
    reader_line = _reader_oneliner(case)
    location = _first_str(case, "location", "kindergarten", "place")

    seen_actions: dict[str, int] = {}
    events: list[str] = []
    for raw in actions:
        action = _as_mapping(raw)
        block = _vevent(
            case_id=case_id,
            title=title,
            action=action,
            stamp=stamp,
            sequence=sequence,
            reader_line=reader_line,
            location=location,
            seen_actions=seen_actions,
        )
        if block:
            events.extend(block)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(title)}",
        f"X-WR-TIMEZONE:{TZID}",
        *_vienna_vtimezone(),
        *events,
        "END:VCALENDAR",
    ]
    text = CRLF.join(_fold(line) for line in lines) + CRLF

    if path is not None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(text.encode("utf-8"))
    return text


def event_uid(case_id: str, action: str, occurrence: int = 1) -> str:
    """Stable UID for (case id, action). Occurrence is 1-based for duplicates."""
    token = _uid_token(action)
    suffix = f"-{occurrence}" if occurrence > 1 else ""
    return f"{_uid_token(case_id)}-{token}{suffix}@{UID_HOST}"


def _vevent(
    *,
    case_id: str,
    title: str,
    action: dict[str, Any],
    stamp: str,
    sequence: int,
    reader_line: str | None,
    location: str | None,
    seen_actions: dict[str, int],
) -> list[str] | None:
    deadline = _first_str(action, "deadline_iso", "deadline", "due")
    if not deadline:
        return None
    name = _first_str(action, "action", "name", "title") or "Termin"
    all_day_flag = _get(action, "all_day")
    if all_day_flag is None:
        all_day_flag = _get(action, "allDay")
    start, all_day = _parse_deadline(deadline, all_day_flag)

    seen_actions[name] = seen_actions.get(name, 0) + 1
    uid = event_uid(case_id, name, seen_actions[name])
    summary = _summary(title, name)
    description = _description(action, reader_line)
    trigger = ALARM_TRIGGER_ALL_DAY if all_day else ALARM_TRIGGER_TIMED
    seq = _int(_get(action, "sequence"), default=sequence)

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp}",
        f"LAST-MODIFIED:{stamp}",
        f"SEQUENCE:{seq}",
        f"SUMMARY:{_escape(summary)}",
        "STATUS:CONFIRMED",
        "CLASS:PRIVATE",
        "TRANSP:TRANSPARENT" if all_day else "TRANSP:OPAQUE",
    ]
    if all_day:
        day = start if isinstance(start, date) and not isinstance(start, datetime) else start.date()
        end = day + timedelta(days=1)
        lines.append(f"DTSTART;VALUE=DATE:{_date_stamp(day)}")
        lines.append(f"DTEND;VALUE=DATE:{_date_stamp(end)}")
    else:
        assert isinstance(start, datetime)
        local = start.astimezone(VIENNA)
        end_iso = _first_str(action, "end_iso", "end")
        if end_iso:
            end_local, _ = _parse_deadline(end_iso, False)
            assert isinstance(end_local, datetime)
            end_wall = end_local.astimezone(VIENNA)
        else:
            end_wall = local + timedelta(hours=1)
        lines.append(f"DTSTART;TZID={TZID}:{_local_stamp(local)}")
        lines.append(f"DTEND;TZID={TZID}:{_local_stamp(end_wall)}")
    if description:
        lines.append(f"DESCRIPTION:{_escape(description)}")
    if location:
        lines.append(f"LOCATION:{_escape(location)}")
    lines.extend(
        [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_escape(summary)}",
            f"TRIGGER:{trigger}",
            f"X-WR-ALARMUID:{uid}-alarm",
            "END:VALARM",
            "END:VEVENT",
        ]
    )
    return lines


def _vienna_vtimezone() -> list[str]:
    # EU DST as published by calendar clients for Europe/Vienna: last Sunday
    # in March (CEST) and last Sunday in October (CET).
    return [
        "BEGIN:VTIMEZONE",
        f"TZID:{TZID}",
        f"X-LIC-LOCATION:{TZID}",
        "BEGIN:DAYLIGHT",
        "TZOFFSETFROM:+0100",
        "TZOFFSETTO:+0200",
        "TZNAME:CEST",
        "DTSTART:19700329T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
        "END:DAYLIGHT",
        "BEGIN:STANDARD",
        "TZOFFSETFROM:+0200",
        "TZOFFSETTO:+0100",
        "TZNAME:CET",
        "DTSTART:19701025T030000",
        "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]


def _parse_deadline(deadline_iso: str, all_day_flag: Any) -> tuple[date | datetime, bool]:
    raw = deadline_iso.strip()
    if _DATE_ONLY.fullmatch(raw):
        day = date.fromisoformat(raw)
        all_day = True if all_day_flag is None else bool(all_day_flag)
        if all_day:
            return day, True
        return datetime(day.year, day.month, day.day, tzinfo=VIENNA), False

    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=VIENNA)
    else:
        dt = dt.astimezone(VIENNA)
    all_day = bool(all_day_flag) if all_day_flag is not None else False
    if all_day:
        return dt.date(), True
    return dt, False


def _summary(title: str, action: str) -> str:
    title = title.strip()
    action = action.strip()
    if not title or title.casefold() == action.casefold():
        return action or title
    return f"{action}: {title}"


def _description(action: dict[str, Any], reader_line: str | None) -> str:
    parts: list[str] = []
    action_reader_line = _reader_oneliner(action)
    line = action_reader_line or reader_line
    if line:
        parts.append(line)
    source = _first_str(action, "source_line", "source", "evidence")
    if source:
        parts.append(source)
    amount = _get(action, "amount")
    if amount is not None and amount != "":
        parts.append(_format_amount(amount))
    return "\n\n".join(parts)


def _reader_oneliner(obj: Any) -> str | None:
    for key in _READER_LINE_KEYS:
        value = _get(obj, key)
        if value:
            return str(value).strip()
    return None


def _format_amount(amount: Any) -> str:
    text = str(amount).strip()
    if "€" in text or "EUR" in text.upper():
        return text
    try:
        number = float(text.replace(",", "."))
    except ValueError:
        return text
    if number.is_integer():
        return f"{int(number)} €"
    return f"{number:.2f} €".replace(".", ",")


def _as_mapping(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, str):
        return dict(json.loads(obj))
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "items") and not isinstance(obj, (bytes, bytearray)):
        try:
            return dict(obj)
        except TypeError:
            pass
    out: dict[str, Any] = {}
    if hasattr(obj, "__dataclass_fields__"):
        for name in obj.__dataclass_fields__:
            out[name] = getattr(obj, name)
        return out
    names = (
        "id",
        "title",
        "actions",
        "sequence",
        "location",
        "kindergarten",
        "place",
        "action",
        "name",
        "deadline_iso",
        "deadline",
        "due",
        "amount",
        "source_line",
        "all_day",
        "allDay",
        "end_iso",
        "end",
        *_READER_LINE_KEYS,
    )
    for name in names:
        if hasattr(obj, name):
            out[name] = getattr(obj, name)
    return out


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _first_str(obj: Any, *keys: str) -> str | None:
    for key in keys:
        value = _get(obj, key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _uid_token(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(text))
    ascii_ = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    token = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_).strip("-.")
    return token.lower() or "item"


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _fold(line: str) -> str:
    data = line.encode("utf-8")
    if len(data) <= _MAX_LINE_OCTETS:
        return line
    parts: list[str] = []
    first = True
    while data:
        limit = _MAX_LINE_OCTETS if first else _MAX_LINE_OCTETS - 1
        chunk = data[:limit]
        while chunk:
            try:
                text = chunk.decode("utf-8")
                break
            except UnicodeDecodeError:
                chunk = chunk[:-1]
        else:
            raise ValueError(f"cannot fold ICS line: {line!r}")
        parts.append(text if first else f" {text}")
        data = data[len(chunk) :]
        first = False
    return CRLF.join(parts)


def _utc_stamp(now: datetime | None) -> str:
    if now is None:
        moment = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        moment = now.replace(tzinfo=timezone.utc)
    else:
        moment = now.astimezone(timezone.utc)
    return moment.strftime("%Y%m%dT%H%M%SZ")


def _date_stamp(day: date) -> str:
    return day.strftime("%Y%m%d")


def _local_stamp(moment: datetime) -> str:
    local = moment.astimezone(VIENNA)
    return local.strftime("%Y%m%dT%H%M%S")
