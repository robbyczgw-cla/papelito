"""AgentCore demo route. Tests never call AWS."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

from web.app import app


def test_agentcore_status_off(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPELITO_DB", str(tmp_path / "cases.db"))
    monkeypatch.setenv("PAPELITO_AGENTCORE_OFF", "1")
    monkeypatch.delenv("PAPELITO_AGENTCORE_ARN", raising=False)
    client = TestClient(app)
    body = client.get("/api/demo/agentcore").json()
    assert body["enabled"] is False
    assert body["region"] == "eu-central-1"
    assert client.post("/api/demo/agentcore").status_code == 503


def test_agentcore_invoke_mocked(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPELITO_DB", str(tmp_path / "cases.db"))
    monkeypatch.delenv("PAPELITO_AGENTCORE_OFF", raising=False)
    monkeypatch.setenv(
        "PAPELITO_AGENTCORE_ARN",
        "configured-runtime",
    )
    monkeypatch.setattr(
        "web.agentcore.invoke_runtime",
        lambda payload, arn=None: {
            "result": {
                "title": "Ausflug in den Tiergarten",
                "runtime": "agentcore",
                "card": {"text": "what  do", "labels": ["what", "do", "by when", "done for you"]},
            }
        },
    )
    client = TestClient(app)
    res = client.post("/api/demo/agentcore?lang=en")
    assert res.status_code == 200
    assert res.json()["result"]["runtime"] == "agentcore"


def test_cases_flag_follows_arn(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPELITO_DB", str(tmp_path / "cases.db"))
    monkeypatch.setenv("PAPELITO_AGENTCORE_OFF", "1")
    client = TestClient(app)
    assert client.get("/api/cases").json()["agentcore"] is False


def test_agentcore_error_does_not_expose_internal_message(monkeypatch):
    monkeypatch.setattr("web.agentcore.agentcore_enabled", lambda: True)

    def fail(_payload):
        raise RuntimeError("private deployment detail")

    monkeypatch.setattr("web.agentcore.invoke_runtime", fail)
    response = TestClient(app).post("/api/demo/agentcore?lang=en")
    assert response.status_code == 502
    assert response.json()["detail"] == {
        "code": "agentcore_failed",
        "message": "AgentCore did not answer",
    }
    assert "private deployment detail" not in response.text


def test_runtime_loader_never_uses_openai_key_for_zen(monkeypatch):
    monkeypatch.delenv("PAPELITO_ZEN_KEY", raising=False)
    monkeypatch.delenv("ZEN_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-provider-key")
    path = Path(__file__).parents[1] / "runtime" / "app" / "Papelito" / "model" / "load.py"
    spec = importlib.util.spec_from_file_location("papelito_runtime_model_load_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._env_key() == ""


def test_runtime_model_error_is_not_a_success_card(monkeypatch):
    monkeypatch.setattr("web.agentcore.agentcore_enabled", lambda: True)
    monkeypatch.setattr("web.agentcore.invoke_runtime", lambda _: {"error": "model_extraction_failed"})
    response = TestClient(app).post("/api/demo/agentcore?lang=en")
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "agentcore_failed"


def test_runtime_call_has_explicit_timeouts_and_no_automatic_replay(monkeypatch):
    import io
    import sys
    from types import SimpleNamespace
    from web.agentcore import invoke_runtime

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("PAPELITO_AGENTCORE_OFF", raising=False)
    observed = {}

    def client(service, **kwargs):
        if service == "sts":
            return SimpleNamespace(get_caller_identity=lambda: {"Arn": "test-principal"})
        observed.update(kwargs)
        def invoke(**kw):
            observed["invoke"] = kw
            return {"response": io.BytesIO(b'{"result": {"ok": true}}')}
        return SimpleNamespace(invoke_agent_runtime=invoke)

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=client))
    assert invoke_runtime({"prompt": "test"}, arn="test-runtime")["result"]["ok"]
    config = observed["config"]
    assert config.connect_timeout == 5
    assert config.read_timeout == 110
    assert config.retries == {"total_max_attempts": 1}
    import hashlib
    assert observed["invoke"]["runtimeUserId"] == "papelito-" + hashlib.sha256(b"test-principal").hexdigest()[:32]
