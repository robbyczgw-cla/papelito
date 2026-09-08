"""Bounded model and AgentCore Identity clients without live network calls."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import logging
import sys
import time
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import boto3
import pytest


REPO = Path(__file__).resolve().parents[1]


def test_zen_clients_have_distinct_stable_session_headers(monkeypatch):
    import papelito.models as models
    monkeypatch.setattr(models, "load_key", lambda: "test-value")
    monkeypatch.setattr(models, "ZEN", "https://opencode.ai/zen/go/v1")
    first = models.text_model()
    second = models.text_model()
    header = first.client_args["default_headers"]["x-opencode-session"]
    assert header and header != second.client_args["default_headers"]["x-opencode-session"]
    assert header == first.client_args["default_headers"]["x-opencode-session"]
    monkeypatch.setattr(models, "ZEN", "https://example.com/v1")
    assert "default_headers" not in models._client_args()


def _model_modules():
    import papelito.models as root_models

    vendored_path = REPO / "runtime" / "app" / "Papelito" / "papelito" / "models.py"
    spec = importlib.util.spec_from_file_location("papelito_vendored_models_test", vendored_path)
    assert spec and spec.loader
    vendored = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vendored)
    return root_models, vendored


def _runtime_modules(name):
    root_module = importlib.import_module(f"papelito.{name}")
    vendored_path = REPO / "runtime" / "app" / "Papelito" / "papelito" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"papelito_vendored_{name}_test", vendored_path)
    assert spec and spec.loader
    vendored = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vendored)
    return root_module, vendored


@pytest.mark.parametrize("factory_name", ["text_model", "vision_model"])
def test_model_factories_set_http_timeout_and_disable_retries(monkeypatch, factory_name):
    for module in _model_modules():
        monkeypatch.setattr(module, "load_key", lambda: "test-value")
        model = getattr(module, factory_name)()

        assert isinstance(model, module.DeadlineOpenAIModel)
        assert model.client_args["timeout"].connect == 5.0
        assert model.client_args["timeout"].read == 40.0
        assert model.client_args["max_retries"] == 0
        if factory_name == "text_model":
            assert model.config["stream"] is False
            assert model.config["params"]["reasoning_effort"] == "none"
        else:
            assert "stream" not in model.config


def test_identity_fails_before_network_without_runtime_workload_token(monkeypatch):
    for module in _model_modules():
        context = SimpleNamespace(get_workload_access_token=lambda: None)
        monkeypatch.setitem(
            __import__("sys").modules,
            "bedrock_agentcore.runtime",
            SimpleNamespace(BedrockAgentCoreContext=context),
        )
        monkeypatch.setattr(boto3, "client", lambda *_args, **_kwargs: pytest.fail("network client created"))

        with pytest.raises(RuntimeError, match="workload token"):
            module._identity_key()


def test_identity_uses_bounded_data_plane_client(monkeypatch):
    for module in _model_modules():
        observed = {}
        context = SimpleNamespace(get_workload_access_token=lambda: "test-workload-token")
        monkeypatch.setitem(
            __import__("sys").modules,
            "bedrock_agentcore.runtime",
            SimpleNamespace(BedrockAgentCoreContext=context),
        )

        class Client:
            def get_resource_api_key(self, **kwargs):
                observed["request"] = kwargs
                return {"apiKey": "test-value"}

        def client(service, **kwargs):
            observed["service"] = service
            observed["client"] = kwargs
            return Client()

        monkeypatch.setattr(boto3, "client", client)
        monkeypatch.setenv("AWS_REGION", "eu-test-1")

        assert module._identity_key() == "test-value"
        assert observed["service"] == "bedrock-agentcore"
        config = observed["client"]["config"]
        assert config.connect_timeout == 5
        assert config.read_timeout == 10
        assert config.retries == {"total_max_attempts": 1}
        assert set(observed["request"]) == {
            "resourceCredentialProviderName",
            "workloadIdentityToken",
        }


def test_key_phase_logs_never_include_value_or_error_detail(monkeypatch, caplog):
    for module in _model_modules():
        caplog.clear()
        monkeypatch.setattr(module, "_load_key", lambda: "test-value")
        with caplog.at_level(logging.INFO, logger=module.__name__):
            assert module.load_key() == "test-value"
        assert "phase=start" in caplog.text
        assert "phase=end" in caplog.text
        assert "test-value" not in caplog.text

        caplog.clear()

        def fail():
            raise TimeoutError("private provider detail")

        monkeypatch.setattr(module, "_load_key", fail)
        with caplog.at_level(logging.INFO, logger=module.__name__):
            with pytest.raises(TimeoutError):
                module.load_key()
        assert "phase=error" in caplog.text
        assert "error_class=TimeoutError" in caplog.text
        assert "private provider detail" not in caplog.text


@pytest.mark.parametrize("module_name", ["extract", "explain"])
def test_runtime_agents_disable_strands_retry_strategy(monkeypatch, module_name):
    for module in _runtime_modules(module_name):
        calls = []

        class Agent:
            def __init__(self, **kwargs):
                calls.append(kwargs)

            def __call__(self, _prompt):
                return "{}"

        monkeypatch.setitem(sys.modules, "strands", SimpleNamespace(Agent=Agent))
        if module_name == "extract":
            module._model_extract("Elternabend am 10. September.", date(2026, 9, 1), object())
        else:
            module.translate_actions(
                [{"action": "Elternabend", "source_line": "Elternabend"}],
                "en",
                object(),
                "Elternabend",
            )

        assert len(calls) == 1
        assert calls[0]["retry_strategy"] is None


def test_model_total_deadline_expires_despite_periodic_chunks(monkeypatch):
    from strands.models.openai import OpenAIModel

    for module in _model_modules():
        state = {"chunks": 0, "closed": False}

        async def periodic_stream(_self, *_args, **_kwargs):
            try:
                while True:
                    await asyncio.sleep(0.01)
                    state["chunks"] += 1
                    yield {"chunk_type": "content_delta"}
            finally:
                state["closed"] = True

        monkeypatch.setattr(OpenAIModel, "stream", periodic_stream)
        monkeypatch.setattr(module, "MODEL_TOTAL_TIMEOUT_SECONDS", 0.05)
        model = module.DeadlineOpenAIModel(client=object(), model_id="test-model")

        async def consume():
            async for _chunk in model.stream([]):
                pass

        started = time.monotonic()
        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(asyncio.wait_for(consume(), timeout=0.3))

        assert time.monotonic() - started < 0.2
        assert state["chunks"] > 0
        assert state["closed"] is True
