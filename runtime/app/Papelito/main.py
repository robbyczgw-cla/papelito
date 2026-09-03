"""Papelito sidecar on AgentCore Runtime.

Extract + explain of Kindergarten note text. No photos, no SQLite, no MCP,
no send. The household PWA and systemd watchdog stay on the machine.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
# In the repository, prefer the root package so local checks exercise the same
# source as the vendored CodeZip package. CodeZip runs from /var/task, where
# the repository parents do not exist and /var/task is already on sys.path.
for _candidate in _HERE.parents:
    if (_candidate / "papelito" / "extract.py").is_file():
        sys.path.insert(0, str(_candidate))
        break

from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()
log = app.logger


@app.entrypoint
def invoke(payload: dict[str, Any], context: Any = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"error": "payload must be a JSON object"}
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        return {"error": "prompt must be a string"}
    from papelito.runtime import extract_and_explain

    log.info("papelito extract_and_explain language=%s", payload.get("language"))
    return extract_and_explain(payload)


if __name__ == "__main__":
    app.run()
