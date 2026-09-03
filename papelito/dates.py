"""Deterministic German/Austrian school-note date parser. No network, no LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

MISS_EMPTY = "empty_phrase"
MISS_RECEIVED = "invalid_received_on"
MISS_NONE = "no_date"
MISS_AMBIGUOUS = "ambiguous"
MISS_INVALID = "invalid_calendar_date"

_WEEKDAYS = {
    "montag": 0,
    "dienstag": 1,
    "mittwoch": 2,
    "donnerstag": 3,
    "freitag": 4,
    "samstag": 5,
    "sonnabend": 5,
    "sonntag": 6,
}

_MONTHS = {
    "januar": 1,
    "jänner": 1,
    "jaenner": 1,
    "jan": 1,
    "jän": 1,
    "februar": 2,
    "feb": 2,
    "märz": 3,
    "maerz": 3,
    "mär": 3,
    "mrz": 3,
    "april": 4,
    "apr": 4,
    "mai": 5,
    "juni": 6,
    "jun": 6,
    "juli": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "oktober": 10,
    "okt": 10,
    "november": 11,
    "nov": 11,
    "dezember": 12,
    "dez": 12,
}

_NUMBER_WORDS = {
    "ein": 1,
    "eins": 1,
    "eine": 1,
    "einem": 1,
    "einen": 1,
    "einer": 1,
    "eines": 1,
    "zwei": 2,
    "drei": 3,
    "vier": 4,
    "fünf": 5,
    "sechs": 6,
    "sieben": 7,
    "acht": 8,
    "neun": 9,
    "zehn": 10,
    "elf": 11,
    "zwölf": 12,
    "zwoelf": 12,
    "dreizehn": 13,
    "vierzehn": 14,
    "fünfzehn": 15,
    "sechzehn": 16,
    "siebzehn": 17,
    "achtzehn": 18,
    "neunzehn": 19,
    "zwanzig": 20,
}

_MONTH_ALT = "|".join(
    re.escape(name) for name in sorted(_MONTHS, key=len, reverse=True)
)
_WEEKDAY_ALT = "|".join(
    re.escape(name) for name in sorted(_WEEKDAYS, key=len, reverse=True)
)
_NUMBER_ALT = "|".join(
    re.escape(name) for name in sorted(_NUMBER_WORDS, key=len, reverse=True)
)

# bis / spätestens immediately before a date or weekday.
_BOUND = re.compile(
    r"(?:bis(?:\s+zum|\s+zu)?|spätestens(?:\s+bis(?:\s+zum)?|\s+am)?)\s*$",
    re.IGNORECASE,
)
_ODER = re.compile(r"\boder\b", re.IGNORECASE)
_RECURRING = re.compile(
    r"\b(?:jeden|jede|jedes|jeweils|regelm[äa]ßig)\b", re.IGNORECASE
)
_NEXT_WEEK = re.compile(
    r"\b(?:n[äa]chste[nrs]?|kommende[nrs]?|folgende[nrs]?)\s+woche\b",
    re.IGNORECASE,
)
_THIS_WEEK = re.compile(
    r"\b(?:diese[nrs]?|aktuellen?)\s+woche\b", re.IGNORECASE
)
_NEXT_MOD = re.compile(
    r"\b(?:n[äa]chste[nrs]?|kommende[nrs]?)\s+$", re.IGNORECASE
)

_TIME = re.compile(
    r"""
    \b\d{1,2}:\d{2}(?:\s*uhr)?\b
    | \b\d{1,2}\.\d{2}\s*uhr\b
    | \b\d{1,2}\s*uhr\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Longest-first: ISO, day + month name, DD.MM.YYYY, DD.MM.
_CALENDAR = re.compile(
    rf"""
    (?P<iso>\b(?P<iso_y>\d{{4}})-(?P<iso_m>\d{{2}})-(?P<iso_d>\d{{2}})\b)
    |
    (?P<named>
        (?P<named_d>\d{{1,2}})\s*\.\s*
        (?P<named_m>{_MONTH_ALT})\.?
        (?:\s+(?P<named_y>\d{{4}}|\d{{2}}))?
    )
    |
    (?P<dmy>
        (?P<dmy_d>\d{{1,2}})\s*\.\s*
        (?P<dmy_m>\d{{1,2}})\s*\.\s*
        (?P<dmy_y>\d{{4}}|\d{{2}})
        (?!\d)
    )
    |
    (?P<dm>
        (?P<dm_d>\d{{1,2}})\s*\.\s*
        (?P<dm_m>\d{{1,2}})
        \.?
        (?!\d)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_DURATION = re.compile(
    rf"""
    \b
    (?:
        innerhalb\s+von
        | innerhalb
        | binnen
        | in\s+den\s+n[äa]chsten
        | in
    )
    \s+
    (?P<num>\d{{1,3}}|{_NUMBER_ALT})
    \s+
    (?P<unit>tagen|tage|tag|wochen|woche)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_WEEKDAY = re.compile(rf"\b(?P<day>{_WEEKDAY_ALT})\b", re.IGNORECASE)

_NAMED_DAY = re.compile(
    r"\b(?P<which>heute|übermorgen|uebermorgen|morgen)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class DateResolution:
    """ISO date on success; miss is a stable reason the confidence gate can ask about."""

    iso: str | None
    miss: str | None = None
    confidence: float = 0.0

    def __bool__(self) -> bool:
        return self.iso is not None and self.miss is None

    def __str__(self) -> str:
        return self.iso or ""


def resolve_dates(phrase: str, received_on: str) -> DateResolution:
    """Parse a school-note date phrase into YYYY-MM-DD.

    ``received_on`` is the ISO day the paper arrived. Relative weekdays resolve
    to the next occurrence on or after that day unless a calendar date is
    present. Ambiguous input returns a structured miss; it never invents a day.
    """
    origin = _parse_iso_day(received_on)
    if origin is None:
        return _miss(MISS_RECEIVED)
    if phrase is None or not str(phrase).strip():
        return _miss(MISS_EMPTY)

    text = _normalize(phrase)
    text = _TIME.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()

    calendar = _resolve_calendar(text, origin)
    if calendar is not None:
        return calendar

    duration = _resolve_duration(text, origin)
    weekday = _resolve_weekday(text, origin)
    named = _resolve_named(text, origin)

    hits = [item for item in (duration, weekday, named) if item is not None]
    if not hits:
        return _miss(MISS_NONE)
    isos = {item.iso for item in hits}
    if len(isos) == 1:
        return hits[0]
    return _miss(MISS_AMBIGUOUS)


def _miss(reason: str) -> DateResolution:
    return DateResolution(iso=None, miss=reason, confidence=0.0)


def _hit(day: date, confidence: float) -> DateResolution:
    return DateResolution(iso=day.isoformat(), miss=None, confidence=confidence)


def _normalize(phrase: str) -> str:
    text = str(phrase).replace("\u00a0", " ")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", text).strip()


def _parse_iso_day(value: str) -> date | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if len(raw) >= 10:
        raw = raw[:10]
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _year_from_token(token: str | None, origin: date) -> int | None:
    if token is None:
        return origin.year
    if len(token) == 2:
        return 2000 + int(token)
    year = int(token)
    if 1900 <= year <= 2100:
        return year
    return None


def _build_day(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _preceded_by_bound(text: str, start: int) -> bool:
    window = text[max(0, start - 28) : start]
    return _BOUND.search(window) is not None


def _resolve_calendar(text: str, origin: date) -> DateResolution | None:
    found: list[tuple[int, date, float]] = []
    saw_token = False
    saw_invalid = False
    for match in _CALENDAR.finditer(text):
        saw_token = True
        parsed, confidence = _calendar_match_to_date(match, origin)
        if parsed is None:
            saw_invalid = True
            continue
        found.append((match.start(), parsed, confidence))

    if not found:
        if saw_token or saw_invalid:
            return _miss(MISS_INVALID)
        return None

    unique_days = {item[1] for item in found}
    if len(unique_days) == 1:
        day, confidence = found[0][1], min(item[2] for item in found)
        return _hit(day, confidence)

    if _ODER.search(text):
        return _miss(MISS_AMBIGUOUS)

    bound = [item for item in found if _preceded_by_bound(text, item[0])]
    bound_days = {item[1] for item in bound}
    if len(bound_days) == 1:
        return _hit(bound[0][1], bound[0][2])
    if len(bound) > 1:
        last = bound[-1]
        return _hit(last[1], last[2])
    return _miss(MISS_AMBIGUOUS)


def _calendar_match_to_date(
    match: re.Match[str], origin: date
) -> tuple[date | None, float]:
    if match.group("iso"):
        day = _build_day(
            int(match.group("iso_y")),
            int(match.group("iso_m")),
            int(match.group("iso_d")),
        )
        return day, 1.0

    if match.group("named"):
        month = _MONTHS[match.group("named_m").lower().rstrip(".")]
        year_token = match.group("named_y")
        year = _year_from_token(year_token, origin)
        if year is None:
            return None, 0.0
        day = _build_day(year, month, int(match.group("named_d")))
        return day, 1.0 if year_token else 0.9

    if match.group("dmy"):
        month = int(match.group("dmy_m"))
        year = _year_from_token(match.group("dmy_y"), origin)
        if year is None:
            return None, 0.0
        day = _build_day(year, month, int(match.group("dmy_d")))
        return day, 1.0

    month = int(match.group("dm_m"))
    day = _build_day(origin.year, month, int(match.group("dm_d")))
    return day, 0.9


def _parse_count(token: str) -> int | None:
    raw = token.lower()
    if raw in _NUMBER_WORDS:
        return _NUMBER_WORDS[raw]
    if raw.isdigit():
        value = int(raw)
        if 1 <= value <= 366:
            return value
    return None


def _resolve_duration(text: str, origin: date) -> DateResolution | None:
    matches = list(_DURATION.finditer(text))
    if not matches:
        return None
    days: list[date] = []
    for match in matches:
        count = _parse_count(match.group("num"))
        if count is None:
            return _miss(MISS_AMBIGUOUS)
        unit = match.group("unit").lower()
        delta = count * 7 if unit.startswith("woche") else count
        days.append(origin + timedelta(days=delta))
    unique = set(days)
    if len(unique) != 1:
        return _miss(MISS_AMBIGUOUS)
    return _hit(days[0], 0.9)


def _weekday_in_week(week_monday: date, weekday: int) -> date:
    return week_monday + timedelta(days=weekday)


def _this_monday(origin: date) -> date:
    return origin - timedelta(days=origin.weekday())


def _next_on_or_after(origin: date, weekday: int) -> date:
    delta = (weekday - origin.weekday()) % 7
    return origin + timedelta(days=delta)


def _next_after(origin: date, weekday: int) -> date:
    delta = (weekday - origin.weekday()) % 7
    if delta == 0:
        delta = 7
    return origin + timedelta(days=delta)


def _resolve_weekday(text: str, origin: date) -> DateResolution | None:
    matches = list(_WEEKDAY.finditer(text))
    if not matches:
        return None
    if _RECURRING.search(text):
        return _miss(MISS_AMBIGUOUS)

    next_week = _NEXT_WEEK.search(text) is not None
    this_week = _THIS_WEEK.search(text) is not None
    if next_week and this_week:
        return _miss(MISS_AMBIGUOUS)

    picked: list[tuple[int, date]] = []
    for match in matches:
        weekday = _WEEKDAYS[match.group("day").lower()]
        if next_week:
            day = _weekday_in_week(_this_monday(origin) + timedelta(days=7), weekday)
        elif this_week:
            day = _weekday_in_week(_this_monday(origin), weekday)
            if day < origin:
                return _miss(MISS_AMBIGUOUS)
        else:
            window = text[max(0, match.start() - 16) : match.start()]
            strict = _NEXT_MOD.search(window) is not None
            day = (
                _next_after(origin, weekday)
                if strict
                else _next_on_or_after(origin, weekday)
            )
        picked.append((match.start(), day))

    unique = {item[1] for item in picked}
    if len(unique) == 1:
        return _hit(picked[0][1], 0.85)

    if _ODER.search(text):
        return _miss(MISS_AMBIGUOUS)

    bound = [item for item in picked if _preceded_by_bound(text, item[0])]
    bound_days = {item[1] for item in bound}
    if len(bound_days) == 1:
        return _hit(bound[0][1], 0.85)
    return _miss(MISS_AMBIGUOUS)


def _resolve_named(text: str, origin: date) -> DateResolution | None:
    matches = list(_NAMED_DAY.finditer(text))
    if not matches:
        return None
    days: list[date] = []
    for match in matches:
        which = match.group("which").lower()
        if which == "heute":
            days.append(origin)
        elif which in {"übermorgen", "uebermorgen"}:
            days.append(origin + timedelta(days=2))
        else:
            days.append(origin + timedelta(days=1))
    unique = set(days)
    if len(unique) != 1:
        return _miss(MISS_AMBIGUOUS)
    return _hit(days[0], 1.0)
