"""End-to-end check of the page's API, without a browser.

    python -m web.selftest

Runs against a throwaway database, so it never touches the real case file.
"""

from __future__ import annotations

import os
import sys
import tempfile


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="papelito-selftest-")
    os.environ["PAPELITO_DB"] = os.path.join(tmp, "cases.db")
    os.environ["PAPELITO_WATCH_LOG"] = os.path.join(tmp, "watchdog-last.json")
    os.environ["PAPELITO_AGENTCORE_OFF"] = "1"

    from fastapi.testclient import TestClient

    from web.app import app

    client = TestClient(app)
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    check("index", client.get("/").status_code == 200)
    away = client.get("/api/cases").json().get("away") or {}
    check("away payload", "nagged" in away and "ran_at" in away)
    check("assets", client.get("/static/app.js").status_code == 200
          and client.get("/static/style.css").status_code == 200)

    seeded = client.post("/api/demo/seed").json()
    cases = seeded["cases"]
    states = [c["state"] for c in cases]
    check("seed", len(cases) == 4, f"{len(cases)} cases via {seeded['backend']}")
    check("due first", states == sorted(states, key=["overdue", "due", "open", "replied"].index),
          " ".join(states))
    check("four columns", all(len(c["labels"]) == 4 for c in cases))
    default_cases = client.get("/api/cases").json()
    german_cases = client.get("/api/cases?lang=de").json()
    check("english default", seeded["lang"] == "en" and default_cases["lang"] == "en"
          and any(c["reminder"] == "Did you send the reply?" for c in default_cases["cases"]))
    ac = client.get("/api/demo/agentcore").json()
    check("agentcore status", ac.get("enabled") is False and ac.get("region") == "eu-central-1",
          str(ac))
    check("agentcore off", client.post("/api/demo/agentcore").status_code == 503)
    check("german overdue", any(c["reminder"] == "Hast du die Antwort geschickt?" for c in german_cases["cases"]))
    watched = client.post("/api/watch").json().get("away") or {}
    check("watch writes last run", bool(watched.get("ran_at")) and int(watched.get("checked") or 0) >= 1,
          f"checked={watched.get('checked')} ran_at={watched.get('ran_at')}")
    check("confidence gate", any(c["question"] for c in cases))
    check("source sentence", all(any(r["source_line"] for r in c["rows"]) for c in cases))

    due = next(c for c in cases if c["state"] == "due")
    ics = client.get(f"/api/cases/{due['id']}/calendar.ics")
    # -P2D and -PT48H are the same 48 hours; the core and the fallback spell it differently.
    alarm = any(t in ics.text for t in ("TRIGGER:-PT48H", "TRIGGER:-P2D"))
    check("ics", ics.status_code == 200 and "BEGIN:VEVENT" in ics.text and alarm)
    reply = client.get(f"/api/cases/{due['id']}/reply.txt")
    check("reply", reply.status_code == 200 and len(reply.text.strip()) > 0)

    ask = next(c for c in cases if c["question"])
    answered = client.post(f"/api/cases/{ask['id']}/answer", data={"answer": "yes"}).json()["case"]
    check("answer", not answered["question"])

    open_before = len(client.get("/api/cases").json()["cases"])
    client.post(f"/api/cases/{due['id']}/done")
    open_after = len(client.get("/api/cases").json()["cases"])
    check("mark done", open_after == open_before - 1, f"{open_before} -> {open_after}")
    check("done still listed", any(c["id"] == due["id"]
          for c in client.get("/api/cases?include_done=true").json()["cases"]))

    check("delete", client.delete(f"/api/cases/{due['id']}").status_code == 200)
    check("delete is real", client.delete(f"/api/cases/{due['id']}").status_code == 404)

    check("reject non-image", client.post(
        "/api/upload", files={"photo": ("x.pdf", b"%PDF", "application/pdf")}).status_code == 400)
    check("reject empty", client.post(
        "/api/upload", files={"photo": ("x.png", b"", "image/png")}).status_code == 400)

    failed = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        print(f"{'ok  ' if ok else 'FAIL'}  {name}{'  (' + detail + ')' if detail else ''}")
    print(f"\n{len(checks) - len(failed)}/{len(checks)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
