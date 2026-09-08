"""Zen OpenAI-compatible model for the Papelito Runtime sidecar."""

from __future__ import annotations

import os

from strands.models.openai import OpenAIModel

ZEN = os.environ.get("OPENAI_BASE_URL", "https://opencode.ai/zen/go/v1")
MODEL_ID = os.environ.get("OPENAI_MODEL_ID", "deepseek-v4-flash")
IDENTITY_PROVIDER_NAME = "ZenKey"
IDENTITY_ENV_VAR = "PAPELITO_ZEN_KEY"


def _env_key() -> str:
    for name in ("PAPELITO_ZEN_KEY", "ZEN_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _get_api_key() -> str:
    env_key = _env_key()
    if env_key:
        return env_key
    if os.getenv("LOCAL_DEV") == "1":
        raise RuntimeError(
            f"{IDENTITY_ENV_VAR} not found. Add {IDENTITY_ENV_VAR}=... to agentcore/.env.local"
        )
    from bedrock_agentcore.identity.auth import requires_api_key

    @requires_api_key(provider_name=IDENTITY_PROVIDER_NAME)
    def _from_identity(api_key: str) -> str:
        return api_key

    return _from_identity()


def load_model() -> OpenAIModel:
    return OpenAIModel(
        client_args={"api_key": _get_api_key(), "base_url": ZEN},
        model_id=MODEL_ID,
        params={"max_tokens": 2000, "temperature": 0.2},
    )
