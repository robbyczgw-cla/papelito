"""Office lookup: PII-stripped query, then a Strands sub-agent over Web Search Plus MCP.

`lookup_office` is Papelito's one sub-agent. The parent tool strips identifiers
before the inner agent ever sees the query. Live search uses Web Search Plus
(`web_search` / `web_extract`). Set ``PAPELITO_LOOKUP_STUB=1`` to skip the MCP
call (tests). Attach recipe: ``docs/research/mcp.md``.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Any, TypedDict

from mcp import StdioServerParameters, stdio_client
from strands import Agent, tool
from strands.tools.mcp import MCPClient

WSP_KEYS_PATH = Path.home() / ".wsp-keys.env"
UVX_COMMAND = "uvx"
UVX_ARGS = ["--from", "web-search-plus-mcp==4.0.3", "web-search-plus-mcp"]

# Profile keys whose values are never sent to search. Longest first so
# ``names`` is not eaten by ``name``.
_PII_KEYS = tuple(
    sorted(
        (
            "children",
            "child",
            "kinder",
            "kind",
            "parents",
            "parent",
            "household",
            "reply_signature",
            "signature",
            "given_name",
            "first_name",
            "last_name",
            "vorname",
            "nachname",
            "names",
            "name",
            "address_line",
            "address",
            "strasse",
            "straße",
            "telephone",
            "phone",
            "handy",
            "mobil",
            "e-mail",
            "email",
            "mail",
            "tel",
        ),
        key=len,
        reverse=True,
    )
)

_KEEP_TOKENS = frozenset(
    {
        "kindergarten",
        "hort",
        "elternverein",
        "gemeinde",
        "amt",
        "magistrat",
        "magistratsabteilung",
        "ma",
        "wien",
        "graz",
        "linz",
        "salzburg",
        "innsbruck",
        "klagenfurt",
        "österreich",
        "osterreich",
        "austria",
        "kontakt",
        "telefon",
        "german",
        "deutsch",
        "english",
        "reader",
        "language",
        "reader_language",
    }
)

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b", re.I)
PHONE_RE = re.compile(
    r"""
    (?:
        (?:\+|00)\s*43(?:[\s./()-]*\d){6,}
      | \b0\d(?:[\s./()-]*\d){6,}
      | \b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b
    )
    """,
    re.VERBOSE,
)
STREET_RE = re.compile(
    r"""
    \b
    [A-ZÄÖÜÁÉÍÓÚ][\wÄÖÜäöüßáéíóúñ.'-]*
    (?:gasse|straße|strasse|str\.|platz|weg|allee|ring|kai|zeile)
    \s+\d+[a-zA-Z]?
    (?:\s*/\s*(?:Stiege|Stg\.?|Tür|Top)\s*\d+[a-zA-Z]?){0,3}
    (?:\s*,\s*\d{4}\s+[A-ZÄÖÜ][\wÄÖÜäöüß-]*)?
    """,
    re.IGNORECASE | re.VERBOSE,
)
PLZ_CITY_RE = re.compile(
    r"\b\d{4}\s+(?:Wien|Graz|Linz|Salzburg|Innsbruck|Klagenfurt|[A-ZÄÖÜ][\wÄÖÜäöüß-]+)\b"
)
_PII_KEY_LINE_RE = re.compile(
    r"(?im)^[ \t]*(?P<key>"
    + "|".join(re.escape(k) for k in _PII_KEYS)
    + r")\s*:\s*[\"']?(?P<val>[^\n\"']+)"
)
_PII_KEY_JSON_RE = re.compile(
    r"(?i)[\"'](?P<key>"
    + "|".join(re.escape(k) for k in _PII_KEYS)
    + r")[\"']\s*:\s*[\"'](?P<val>[^\"']+)"
)
_PII_KEY_LOOSE_RE = re.compile(
    r"(?i)\b(?P<key>"
    + "|".join(re.escape(k) for k in _PII_KEYS)
    + r")\b\s*:?\s+[\"']?(?P<val>[A-ZÄÖÜÁÉÍÓÚÑ][\wÄÖÜäöüßáéíóúñ'-]*"
    r"(?:\s+[A-ZÄÖÜÁÉÍÓÚÑ][\wÄÖÜäöüßáéíóúñ'-]*){0,3})"
)
_INSTITUTION_KEY_RE = re.compile(
    r"(?im)^[ \t]*(?:kindergarten|hort|elternverein|gemeinde|amt|institution|office|schule)"
    r"\s*:\s*[\"']?([^\n\"']+)"
)
_INSTITUTION_PHRASE_RE = re.compile(
    r"(?i)\b((?:Kindergarten|Hort|Elternverein|Gemeinde|Magistrat(?:sabteilung)?)\s+[^,\n]+)"
)
_MA_RE = re.compile(r"\bMA\s*\d+\b", re.I)

LOOKUP_SYSTEM_PROMPT = """\
You look up public contact details for Austrian Kindergarten, Hort, Elternverein,
Gemeinde, Magistrat, and MA offices.

The user query is already stripped of family names, children, household addresses,
and private phone numbers. Do not add any of those. Do not invent a phone number
or street. If a field is missing from the sources, return null.

Use web_search with the query as given (country Austria). If an official page is
clear, you may web_extract it.

Reply with JSON only, no markdown:
{"what": string|null, "where": string|null, "phone": string|null, "url": string|null}
- what: the institution or office
- where: the office's public address from a source
- phone: a public switchboard number from a source
- url: the source page
"""


class OfficeContact(TypedDict, total=False):
    what: str | None
    where: str | None
    phone: str | None
    url: str | None
    query: str
    stub: bool
    error: str


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _name_token_re(token: str) -> re.Pattern[str]:
    """Match a name token with or without Latin accents."""
    classes = {
        "a": "aáàäâã",
        "e": "eéèëê",
        "i": "iíìïî",
        "o": "oóòöôõ",
        "u": "uúùüû",
        "n": "nñ",
        "c": "cç",
    }
    parts: list[str] = []
    for ch in token:
        base = _fold(ch).lower()
        if base in classes:
            chars = classes[base]
            parts.append("[" + chars + chars.upper() + "]")
        elif ch.isalnum() or ch in "-'":
            parts.append(re.escape(ch))
        else:
            parts.append(re.escape(ch))
    return re.compile(r"\b" + "".join(parts) + r"\b", re.I)


def office_name_from(text: str) -> str:
    """Institution / Amt name, ignoring household fields."""
    key = _INSTITUTION_KEY_RE.search(text)
    if key:
        return key.group(1).strip().strip("\"'")
    ma = _MA_RE.search(text)
    if ma:
        return re.sub(r"\s+", " ", ma.group(0)).strip()
    phrase = _INSTITUTION_PHRASE_RE.search(text)
    if phrase:
        return phrase.group(1).strip().strip("\"'")
    cleaned = " ".join(strip_pii(text).split())
    return cleaned


def _pii_values(text: str) -> list[str]:
    values: list[str] = []
    for rx in (_PII_KEY_LINE_RE, _PII_KEY_JSON_RE, _PII_KEY_LOOSE_RE):
        for match in rx.finditer(text):
            val = match.group("val").strip().strip("\"'").strip()
            if val:
                values.append(val)
    values.sort(key=len, reverse=True)
    return values


def strip_pii(text: str) -> str:
    """Remove emails, phones, street addresses, and given/household names.

    Keeps Kindergarten / Gemeinde / Hort / MA institution names so the query
    builder still has something to search.
    """
    if not text:
        return ""
    office = office_name_from(text) if _INSTITUTION_KEY_RE.search(text) or _INSTITUTION_PHRASE_RE.search(text) or _MA_RE.search(text) else ""
    protect = {t.lower() for t in re.findall(r"[\wÄÖÜäöüßáéíóúñ'-]+", office, re.I)}

    out = text
    for val in _pii_values(out):
        out = out.replace(val, " ")
        folded = _fold(val)
        if folded != val:
            out = re.sub(re.escape(val), " ", out, flags=re.I)

    out = EMAIL_RE.sub(" ", out)
    out = PHONE_RE.sub(" ", out)
    out = STREET_RE.sub(" ", out)
    out = PLZ_CITY_RE.sub(" ", out)

    for val in _pii_values(text):
        for token in re.findall(r"[\wÄÖÜäöüßáéíóúñ'-]+", val, re.I):
            if len(token) < 2:
                continue
            if token.lower() in _KEEP_TOKENS or token.lower() in protect:
                continue
            if token.isdigit():
                continue
            out = _name_token_re(token).sub(" ", out)

    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def build_office_query(name: str) -> str:
    """Public-web query. Keeps the office/Kindergarten name; no household PII.

    Shapes from the spec:
    ``Kindergarten [name] Wien Kontakt`` or ``Gemeinde [name] Amt Telefon``.
    """
    office = office_name_from(name)
    office = " ".join(strip_pii(office).split())
    office = office.strip(" :,-")
    if not office:
        return ""

    lowered = office.lower()
    if _MA_RE.fullmatch(office) or lowered.startswith("ma "):
        return f"{office} Wien Amt Telefon"
    if any(tag in lowered for tag in ("gemeinde", "amt", "magistrat", "bezirk")):
        core = re.sub(r"^(die\s+)?(gemeinde|amt|magistrat(?:sabteilung)?)\s+", "", office, flags=re.I)
        core = core.strip() or office
        return f"Gemeinde {core} Amt Telefon"
    if lowered.startswith("hort"):
        return f"{office} Wien Kontakt"
    if lowered.startswith("elternverein"):
        return f"{office} Wien Kontakt"
    if lowered.startswith("kindergarten"):
        return f"{office} Wien Kontakt"
    return f"Kindergarten {office} Wien Kontakt"


def load_wsp_env() -> dict[str, str]:
    """Merge process env with ``~/.wsp-keys.env``. Never log values."""
    env = {k: v for k, v in os.environ.items() if isinstance(v, str)}
    if not WSP_KEYS_PATH.is_file():
        return env
    for raw in WSP_KEYS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key:
            env[key] = val
    return env


def make_wsp_client() -> MCPClient:
    """Attach Web Search Plus MCP over stdio (uvx pin 4.0.3)."""
    return MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command=UVX_COMMAND,
                args=list(UVX_ARGS),
                env=load_wsp_env(),
            )
        ),
        tool_filters={"allowed": ["web_search", "web_extract"]},
        startup_timeout=90,
    )


def _text_model() -> Any | None:
    """Prefer ``papelito.models.text_model`` (owned by the strands agent)."""
    try:
        from papelito.models import text_model

        return text_model()
    except Exception:
        return None


def make_lookup_subagent(
    mcp_client: MCPClient,
    *,
    model: Any | None = None,
) -> Agent:
    """Inner Strands agent: Web Search Plus tools only, PII-free queries."""
    return Agent(
        name="lookup_office",
        description=(
            "Look up public what/where/phone + URL for an Austrian "
            "Kindergarten, Hort, Gemeinde, or MA office. Query has no PII."
        ),
        model=model if model is not None else _text_model(),
        tools=[mcp_client],
        system_prompt=LOOKUP_SYSTEM_PROMPT,
        callback_handler=None,
    )


def _stub_mcp_search(query: str, reason: str = "stub") -> OfficeContact:
    """STUB: live Web Search Plus MCP call.

    Used when ``PAPELITO_LOOKUP_STUB`` is set, uvx/MCP cannot start, or the
    text model is missing. The query is still the PII-stripped office search.
    Attach the server with the snippet in ``docs/research/mcp.md``.
    """
    return {
        "what": None,
        "where": None,
        "phone": None,
        "url": None,
        "query": query,
        "stub": True,
        "error": reason,
    }


def _use_stub() -> bool:
    flag = os.environ.get("PAPELITO_LOOKUP_STUB", "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _parse_office_json(text: str, query: str) -> OfficeContact:
    data: OfficeContact = {
        "what": None,
        "where": None,
        "phone": None,
        "url": None,
        "query": query,
        "stub": False,
    }
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict):
            for key in ("what", "where", "phone", "url"):
                val = obj.get(key)
                if val in ("", "null", "None"):
                    val = None
                if val is not None:
                    val = str(val).strip()
                data[key] = val  # type: ignore[literal-required]
            return data
    url = re.search(r"https?://[^\s)\"'>]+", text)
    phone = PHONE_RE.search(text)
    snippet = text.strip()[:500] or None
    data["what"] = snippet
    data["url"] = url.group(0).rstrip(".,;") if url else None
    data["phone"] = phone.group(0).strip() if phone else None
    return data


def _tool_result_text(result: Any) -> str:
    chunks: list[str] = []
    if isinstance(result, dict):
        for block in result.get("content") or []:
            if isinstance(block, dict) and block.get("text"):
                chunks.append(str(block["text"]))
            elif isinstance(block, str):
                chunks.append(block)
        structured = result.get("structuredContent")
        if structured:
            chunks.append(json.dumps(structured, ensure_ascii=False))
    return "\n".join(chunks)


def _direct_web_search(client: MCPClient, query: str) -> OfficeContact:
    result = client.call_tool_sync(
        tool_use_id=str(uuid.uuid4()),
        name="web_search",
        arguments={"query": query, "provider": "auto", "count": 5, "country": "at"},
    )
    text = _tool_result_text(result)
    parsed = _parse_office_json(text, query)
    parsed["query"] = query
    parsed["stub"] = False
    return parsed


def _run_lookup_subagent(query: str) -> OfficeContact:
    model = _text_model()
    client = make_wsp_client()
    with client:
        if model is None:
            return _direct_web_search(client, query)
        agent = make_lookup_subagent(client, model=model)
        result = agent(
            "Search for public contact details using this exact query:\n"
            f"{query}\n"
            "Return JSON only with what, where, phone, url."
        )
        parsed = _parse_office_json(str(result), query)
        parsed["query"] = query
        parsed["stub"] = False
        return parsed


def lookup_office_contact(name: str) -> OfficeContact:
    """Strip PII, build the office query, then search (or stub)."""
    query = build_office_query(name)
    if not query:
        return _stub_mcp_search("", "no office name after PII strip")
    if _use_stub():
        return _stub_mcp_search(query, "PAPELITO_LOOKUP_STUB")
    try:
        return _run_lookup_subagent(query)
    except Exception as exc:
        return _stub_mcp_search(query, f"mcp unavailable: {type(exc).__name__}")


@tool(name="lookup_office")
def lookup_office(name: str) -> dict[str, Any]:
    """Look up public contact for an Austrian Kindergarten, Hort, Gemeinde, or MA office.

    Child names, household addresses, phones, emails, and the profile blob are
    stripped before Web Search Plus runs. Returns what / where / phone / url.

    Args:
        name: Institution or office name. A profile blob is accepted; PII is stripped.

    Returns:
        Dict with what, where, phone, url, and the PII-stripped query actually searched.
    """
    return dict(lookup_office_contact(name))
