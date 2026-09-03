"""Zen OpenAI-compatible model factory for Papelito.

Uses strands-agents 1.54.0 ``strands.models.openai.OpenAIModel`` against the
Zen gateway. Key is never printed or logged.

Vision input shape (see ``tools/gate0.py`` and ``strands.types.content.ContentBlock``)::

    agent([
        {"text": "..."},
        {"image": {"format": "png", "source": {"bytes": png}}},
    ])

Vision calls need ``max_tokens >= 2000``. Do not send gpt-5.6-luna, muse-spark,
or gemini through this gateway (HTTP 500).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from strands.models.openai import OpenAIModel

ZEN = os.environ.get("OPENAI_BASE_URL", "https://opencode.ai/zen/go/v1")
AUTH_JSON = Path.home() / ".pi" / "agent" / "auth.json"
IDENTITY_PROVIDER_NAME = "ZenKey"

VISION_MODEL_ID = "deepseek-v4-flash-vision-exp"
TEXT_MODEL_ID = "deepseek-v4-flash"


def load_key() -> str:
    """Return the Zen API key from env or ``~/.pi/agent/auth.json``.

    Env: ``PAPELITO_ZEN_KEY`` or ``ZEN_API_KEY``. Auth.json path on this
    machine is ``opencode-go.key``. The value is never printed or logged.
    ``OPENAI_API_KEY`` is not used here: that key must not be sent to Zen.
    """
    for name in ("PAPELITO_ZEN_KEY", "ZEN_API_KEY"):
        env_key = os.environ.get(name, "").strip()
        if env_key:
            return env_key

    try:
        payload = json.loads(AUTH_JSON.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        if os.getenv("LOCAL_DEV") != "1":
            return _identity_key()
        raise RuntimeError(
            "Zen key not found: set PAPELITO_ZEN_KEY or ZEN_API_KEY, or provide ~/.pi/agent/auth.json"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Zen auth.json is not valid JSON") from exc

    try:
        key = payload["opencode-go"]["key"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            "Zen key not found in ~/.pi/agent/auth.json (expected opencode-go.key)"
        ) from exc

    if not isinstance(key, str) or not key.strip():
        raise RuntimeError("Zen key in ~/.pi/agent/auth.json is empty")
    return key.strip()


def _identity_key() -> str:
    """Fetch the deployed Zen key from the AgentCore Identity provider."""
    from bedrock_agentcore.identity.auth import requires_api_key

    @requires_api_key(provider_name=IDENTITY_PROVIDER_NAME)
    def _from_identity(api_key: str) -> str:
        return api_key

    return _from_identity()


def vision_model() -> OpenAIModel:
    """Vision model for reading note photos (deepseek-v4-flash-vision-exp)."""
    return OpenAIModel(
        client_args={"api_key": load_key(), "base_url": ZEN},
        model_id=VISION_MODEL_ID,
        params={"max_tokens": 2500, "temperature": 0},
    )


def text_model() -> OpenAIModel:
    """Text model for tools, cards, replies, and the lookup sub-agent."""
    return OpenAIModel(
        client_args={"api_key": load_key(), "base_url": ZEN},
        model_id=TEXT_MODEL_ID,
        params={"max_tokens": 2000, "temperature": 0.2},
    )
