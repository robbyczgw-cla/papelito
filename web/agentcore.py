"""Invoke the Papelito AgentCore Runtime sidecar (extract + explain of seed text)."""

from __future__ import annotations

import json
import hashlib
import os
import uuid
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
ARN_FILE = REPO / "runtime" / "agentcore" / ".arn"
REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "eu-central-1"


def agentcore_arn() -> str | None:
    """Runtime ARN from env, or the gitignored file written after deploy.

    Tests that set PAPELITO_AGENTCORE_OFF=1 never read the file, so selftest
    cannot spend AWS money. PYTEST_CURRENT_TEST blocks the boto3 call in
    invoke_runtime, not this lookup, so mocked route tests can still see enabled.
    """
    if os.environ.get("PAPELITO_AGENTCORE_OFF") == "1":
        return None
    env = os.environ.get("PAPELITO_AGENTCORE_ARN", "").strip()
    if env:
        return env
    try:
        value = ARN_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return value or None


def agentcore_enabled() -> bool:
    return bool(agentcore_arn())


def _decode_response(response: dict[str, Any]) -> dict[str, Any]:
    raw = response.get("response")
    if raw is None:
        raise RuntimeError("AgentCore returned an empty response")
    if hasattr(raw, "read"):
        body = raw.read()
        text = body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)
        return json.loads(text)
    chunks: list[str] = []
    for chunk in raw:
        chunks.append(chunk.decode("utf-8") if isinstance(chunk, (bytes, bytearray)) else str(chunk))
    return json.loads("".join(chunks))


def invoke_runtime(payload: dict[str, Any], arn: str | None = None) -> dict[str, Any]:
    """SigV4 InvokeAgentRuntime. Runtime stays private; judges never hit it."""
    if os.environ.get("PAPELITO_AGENTCORE_OFF") == "1" or os.environ.get("PYTEST_CURRENT_TEST"):
        raise RuntimeError("AgentCore is disabled in tests")
    runtime_arn = arn or agentcore_arn()
    if not runtime_arn:
        raise RuntimeError("PAPELITO_AGENTCORE_ARN is not set")
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "bedrock-agentcore",
        region_name=REGION,
        config=Config(
            connect_timeout=5,
            read_timeout=110,
            retries={"total_max_attempts": 1},
        ),
    )
    identity = boto3.client(
        "sts", region_name=REGION,
        config=Config(connect_timeout=5, read_timeout=5, retries={"total_max_attempts": 1}),
    ).get_caller_identity()
    runtime_user = "papelito-" + hashlib.sha256(identity["Arn"].encode("utf-8")).hexdigest()[:32]
    response = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        runtimeSessionId=str(uuid.uuid4()),
        runtimeUserId=runtime_user,
        qualifier="DEFAULT",
        payload=json.dumps(payload).encode("utf-8"),
    )
    return _decode_response(response)


def seed_payload(language: str) -> dict[str, Any]:
    from papelito.runtime import DEFAULT_RECEIVED_ON, DEFAULT_TEXT

    return {
        "prompt": "extract_and_explain",
        "text": DEFAULT_TEXT,
        "received_on": DEFAULT_RECEIVED_ON,
        "language": language,
    }
