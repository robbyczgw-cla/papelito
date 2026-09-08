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

import asyncio
import json
import logging
import os
import time
import uuid
from urllib.parse import urlparse
from pathlib import Path

import httpx
from strands.models.openai import OpenAIModel

ZEN = os.environ.get("OPENAI_BASE_URL", "https://opencode.ai/zen/go/v1")
AUTH_JSON = Path.home() / ".pi" / "agent" / "auth.json"
IDENTITY_PROVIDER_NAME = "ZenKey"

VISION_MODEL_ID = "deepseek-v4-flash-vision-exp"
TEXT_MODEL_ID = "deepseek-v4-flash"
MODEL_HTTP_TIMEOUT = httpx.Timeout(40.0, connect=5.0)
MODEL_TOTAL_TIMEOUT_SECONDS = 45.0
MODEL_MAX_RETRIES = 0
IDENTITY_CONNECT_TIMEOUT_SECONDS = 5
IDENTITY_READ_TIMEOUT_SECONDS = 10
IDENTITY_MAX_ATTEMPTS = 1

log = logging.getLogger(__name__)


class DeadlineOpenAIModel(OpenAIModel):
    """OpenAI-compatible model with a total deadline across streamed chunks."""

    async def stream(self, *args, **kwargs):
        started = time.monotonic()
        upstream = super().stream(*args, **kwargs)
        try:
            while True:
                remaining = MODEL_TOTAL_TIMEOUT_SECONDS - (time.monotonic() - started)
                if remaining <= 0:
                    raise asyncio.TimeoutError("model total deadline exceeded")
                try:
                    chunk = await asyncio.wait_for(upstream.__anext__(), timeout=remaining)
                except StopAsyncIteration:
                    return
                yield chunk
        finally:
            try:
                await upstream.aclose()
            except Exception as exc:
                log.warning("model_stream_close phase=error error_class=%s", type(exc).__name__)


def load_key() -> str:
    """Return the Zen API key from env or ``~/.pi/agent/auth.json``.

    Env: ``PAPELITO_ZEN_KEY`` or ``ZEN_API_KEY``. Auth.json path on this
    machine is ``opencode-go.key``. The value is never printed or logged.
    ``OPENAI_API_KEY`` is not used here: that key must not be sent to Zen.
    """
    started = time.monotonic()
    log.info("zen_key phase=start")
    try:
        key = _load_key()
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        log.warning("zen_key phase=error elapsed_ms=%d error_class=%s", elapsed_ms, type(exc).__name__)
        raise
    elapsed_ms = int((time.monotonic() - started) * 1000)
    log.info("zen_key phase=end elapsed_ms=%d", elapsed_ms)
    return key


def _load_key() -> str:
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
    """Fetch the deployed Zen key with bounded AgentCore data-plane calls."""
    from bedrock_agentcore.runtime import BedrockAgentCoreContext
    import boto3
    from botocore.config import Config

    workload_token = BedrockAgentCoreContext.get_workload_access_token()
    if not isinstance(workload_token, str) or not workload_token.strip():
        raise RuntimeError("AgentCore workload token is unavailable")
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if not region:
        raise RuntimeError("AWS region is unavailable")
    client = boto3.client(
        "bedrock-agentcore",
        region_name=region,
        config=Config(
            connect_timeout=IDENTITY_CONNECT_TIMEOUT_SECONDS,
            read_timeout=IDENTITY_READ_TIMEOUT_SECONDS,
            retries={"total_max_attempts": IDENTITY_MAX_ATTEMPTS},
        ),
    )
    response = client.get_resource_api_key(
        resourceCredentialProviderName=IDENTITY_PROVIDER_NAME,
        workloadIdentityToken=workload_token.strip(),
    )
    key = response.get("apiKey") if isinstance(response, dict) else None
    if not isinstance(key, str) or not key.strip():
        raise RuntimeError("AgentCore Identity returned no API key")
    return key.strip()


def _client_args() -> dict:
    args = {
        "api_key": load_key(),
        "base_url": ZEN,
        "timeout": MODEL_HTTP_TIMEOUT,
        "max_retries": MODEL_MAX_RETRIES,
    }
    if urlparse(ZEN).hostname == "opencode.ai":
        # Per-client affinity, stable over its tool calls and never a user ID.
        args["default_headers"] = {
            "x-opencode-session": str(uuid.uuid4()),
            "User-Agent": "papelito/0.1.0",
        }
    return args


def vision_model() -> OpenAIModel:
    """Vision model for reading note photos (deepseek-v4-flash-vision-exp)."""
    return DeadlineOpenAIModel(
        client_args=_client_args(),
        model_id=VISION_MODEL_ID,
        params={"max_tokens": 2500, "temperature": 0},
    )


def text_model() -> OpenAIModel:
    """Text model for tools, cards, replies, and the lookup sub-agent."""
    return DeadlineOpenAIModel(
        client_args=_client_args(),
        model_id=TEXT_MODEL_ID,
        params={
            "max_tokens": 2000,
            "temperature": 0.2,
            "reasoning_effort": "none",
        },
        stream=False,
    )
