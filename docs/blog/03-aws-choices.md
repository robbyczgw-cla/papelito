Agents for Humans: AgentCore Runtime sidecar, watchdog stays on systemd

This is the third post about Papelito, an Everyday Agents entry that reads Kindergarten paper and tracks the case through its reminder window. The first post covers the product boundary and the second covers the tools. This one explains the live AgentCore Runtime sidecar and why the daily watchdog remains on systemd.

## What runs where today

| Piece | Where it runs | Why |
| --- | --- | --- |
| The agent and its tools | Strands Agents SDK and Python on a local machine | The local workflow stays with its case file |
| Vision and text models | Zen through an OpenAI-compatible gateway | Uses `deepseek-v4-flash-vision-exp` for photos and `deepseek-v4-flash` for text |
| Case file | SQLite on the local machine | Contains the case state |
| Photos and generated artifacts | Local disk | Remain with the case |
| Web page | FastAPI on the household machine; separate Lightsail judge sandbox | Household data stays local; judge data is synthetic only |
| Watchdog | systemd user timer, daily | By default, it needs only the case file and the clock |
| Runtime sidecar | Private Amazon Bedrock AgentCore Runtime endpoint in `eu-central-1` | Extracts and explains text sent by the PWA demo route |
| Office lookup | Web Search Plus MCP over stdio | Identifiers stripped first |

The local workflow does not depend on the Runtime sidecar. A local PWA exposes a separate "Run on AgentCore" button. Its demo route sends one fixed, invented note as text to the private Runtime endpoint. It never sends an uploaded photo or the SQLite case file.

## Strands did real work

Papelito is built with Strands Agents, the open-source SDK from AWS. Two parts of the SDK mattered to this implementation.

The `@tool` decorator turns a docstring and a type signature into a tool the model can call, so the tool definitions and the code are the same file. Changing the `match_case` scoring does not require updating a separate schema.

`OpenAIModel` takes a `base_url`. Strands defaults to Bedrock when no model is passed, and the official examples show the same class with a custom URL. The Zen gateway uses that interface.

```python
from strands.models.openai import OpenAIModel
vision = OpenAIModel(client_args={"api_key": key, "base_url": ZEN_URL}, model_id="deepseek-v4-flash-vision-exp",
                     params={"max_tokens": 2500, "temperature": 0})
```

The models are not Bedrock Claude models. Zen handled the photo and text paths through the OpenAI-compatible gateway. The gateway also needs a per-client session header and its own timeout and retry setup, so switching providers is a small amount of client configuration rather than a bare constructor call. Strands still fit this build because the model class accepts a custom base URL.

## Why the photos and case file stay local

Kindergarten paper may contain personal data. Two rules follow.

The photo is sent only for the vision call that transcribes it. The transcription, German source lines, calendar file and reply draft are stored with the case on local disk. Text-model calls can also include the transcription, source lines, relevant case details and approved profile names. Deleting a case removes its related rows from SQLite, vacuums the database, unlinks app-managed photos referenced only by that case, and removes the case's exact `.ics` and reply filenames. It never deletes a user-supplied source file outside the app-managed private photo directory. There is no soft delete.

A household install has no public upload route and no public URL. The judge demo at https://d3cknd2hkoyhzh.cloudfront.net is a separate build, password-protected, on one Lightsail instance in `eu-central-1`. It is preloaded only with synthetic names, photos and cases, and judges use the supplied synthetic demo photos. No household photo is on AWS. Judge credentials must be supplied through an access-restricted channel after confirming who can view that channel.

Those two rules also draw the AgentCore boundary in the next section.

## AgentCore: what fits, and what does not

The AgentCore boundary follows one question: which parts of Papelito belong on Runtime, and which do not?

AgentCore Runtime is deployed in `eu-central-1`. The local PWA demo route's preset synthetic note states that the outing is on 2026-09-09 and the 8 euro payment is due on 2026-09-07. A successful invocation returns the extracted card with `runtime: agentcore`. What follows is why the watchdog is still not on it.

**What fits.** Runtime hosts Papelito's extract-and-explain path behind a private invocation endpoint. The entry point validates the JSON payload, requires a string prompt, then passes the payload to the same extract and explain function used by the local application. The note text comes from the request. It is not hardcoded into the entry point. The same `OpenAIModel` with a custom base URL runs there, and the gateway key goes into AgentCore Identity as an API-key credential.

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload, context=None):
    if not isinstance(payload, dict):
        return {"error": "payload must be a JSON object"}
    if not isinstance(payload.get("prompt"), str):
        return {"error": "prompt must be a string"}
    from papelito.runtime import extract_and_explain
    return extract_and_explain(payload)

if __name__ == "__main__":
    app.run()
```

The on-demand work maps onto that. Extract the actions, explain the card. Each is a request with an answer. Runtime accepts note text in the invocation payload. In the recorded live call, the local PWA sends a preset, invented German note to the private endpoint with IAM SigV4. The returned card includes the outing on 2026-09-09 and the 8 euro payment due on 2026-09-07. Dead wait time is trimmed. This route sends no photo at all. That differs from the normal vision path, which does send a photo to the external vision provider for transcription.

**What does not fit.** The watchdog. Three reasons, and none of them is that AgentCore is bad.

Runtime has no scheduler of its own. Scheduling it would add EventBridge Scheduler or another service, IAM work and retries to replace a two-line systemd timer.

Each session is an isolated microVM with ephemeral disk. The watchdog's whole job is to open `data/papelito.db`, find the cases due in two days, and write a due flag back. On Runtime the case state would have to live in durable cloud storage instead of on the local disk. The photos would not have to move with it, but the case file leaving the local machine already changes the rule from the previous section, and the product becomes a different product.

The local machine already has the case file and the clock. By default, its daily timer does not need the network. The README says this plainly, and so does this post.

## The plan through judging

Judging runs from 15 September to 8 October 2026. Through that window judges get a password-protected demo at https://d3cknd2hkoyhzh.cloudfront.net. It is the same FastAPI app, SQLite case file and daily systemd timer, on a single Lightsail instance in `eu-central-1` behind a Lightsail distribution with no cache. It is preloaded only with synthetic names, photos and cases, and judges use the supplied synthetic demo photos. Judge credentials must be supplied through an access-restricted channel after confirming who can view that channel.

That build is the hosted judge sandbox. It has AgentCore disabled and carries no AWS credentials. The Runtime sidecar is separate and stays live for extract and explain. The video was prepared privately and will accompany the submission. It shows one live PWA call to the Runtime endpoint, followed by the architecture diagram. No AWS console appears in the cut.

Household deployments stay local. Web page, timer, case file and photos remain on the parent's machine. The watchdog stays on systemd everywhere, demo included.

The repository is private until submission, when it will be released under MIT at https://github.com/robbyczgw-cla/papelito. The only pre-existing component is Web Search Plus MCP, published before the hackathon. Everything else was written in the submission period with help from AI coding assistants, as disclosed in the submission.
