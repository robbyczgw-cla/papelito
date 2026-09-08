# Papelito on AgentCore Runtime

Sidecar that runs Papelito's `extract` and `explain` steps for Kindergarten note text on Amazon Bedrock AgentCore Runtime. It does nothing else: no photos, no SQLite, no MCP, no calendar, no reply drafting, no watchdog. Those stay on the household machine.

## Layout

- `main.py`: `BedrockAgentCoreApp` with one `@app.entrypoint`. It rejects non-object payloads and non-string `prompt`, then calls `papelito.runtime.extract_and_explain(payload)`. In the repository it prefers the root `papelito` package; in CodeZip it uses the vendored package.
- `papelito/`: vendored copy of `extract.py`, `explain.py`, `models.py` and `runtime.py`.
- `pyproject.toml`: Runtime and model dependencies.

## Run locally

From this directory:

```bash
uv sync --locked
uv run python main.py
```

The server listens on `0.0.0.0:8080`. Example synthetic payload:

```bash
curl -s localhost:8080/invocations -H 'content-type: application/json' -d '{
  "prompt": "Liebe Eltern, am Mittwoch 09.09.2026 gehen wir in den Tiergarten. Bitte 8 Euro bis Montag 07.09.2026 mitbringen.",
  "language": "en"
}'
```

## Model and credentials

`papelito/models.py` builds a Strands `OpenAIModel` against the Zen OpenAI-compatible gateway. `OPENAI_BASE_URL` overrides the default. The text model is `deepseek-v4-flash`, with a 45-second total deadline and no retries.

The key is resolved in this order:

1. `PAPELITO_ZEN_KEY`, then `ZEN_API_KEY`.
2. The local Pi credentials file, `opencode-go.key`.
3. If that file is missing and `LOCAL_DEV` is not `1`: AgentCore Identity, using the workload access token and the API-key provider named `ZenKey`, in `AWS_REGION` or `AWS_DEFAULT_REGION`.

`OPENAI_API_KEY` is deliberately ignored. Missing credentials raise an explicit error. The key is never logged.

## Deployment

Account-specific AgentCore configuration is intentionally not shipped. `agentcore deploy` does not work from this folder; wire it into your own AgentCore project.
