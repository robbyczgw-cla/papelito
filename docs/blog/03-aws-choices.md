Agents for Humans: AgentCore Runtime sidecar, watchdog stays on systemd

This is the third post about Papelito, an Everyday Agents entry that reads Kindergarten paper and keeps the case open until the parent taps done. The first post covers the product boundary and the second covers the tools. This one explains the live AgentCore Runtime sidecar and why the daily watchdog remains on systemd.

## What runs where today

| Piece | Where it runs | Why |
| --- | --- | --- |
| The agent and its tools | Strands Agents SDK and Python on a local machine | The local workflow stays with its case file |
| Vision and text models | Zen through an OpenAI-compatible gateway | Uses `deepseek-v4-flash-vision-exp` for photos and `deepseek-v4-flash` for text |
| Case file | SQLite on the local machine | Contains the case state |
| Photos and crops | Local disk | Remain with the case |
| Web page | FastAPI on the local machine | Private, never a public demo URL |
| Watchdog | systemd user timer, daily | Needs the case file and the clock, nothing else |
| Runtime sidecar | Amazon Bedrock AgentCore Runtime in `eu-central-1` | Extract and explain of fixed, invented seed text |
| Office lookup | Web Search Plus MCP over stdio | Identifiers stripped first |

The local workflow does not depend on the Runtime sidecar. The PWA exposes a separate "Run on AgentCore" button for the fixed seed text. It never sends an uploaded photo or the SQLite case file.

## Strands is the AWS piece, and it did real work

Papelito is built with Strands Agents, the open-source SDK from AWS. Two parts of the SDK mattered to this implementation.

The `@tool` decorator turns a docstring and a type signature into a tool the model can call, so the tool definitions and the code are the same file. Changing the `match_case` scoring does not require updating a separate schema.

`OpenAIModel` takes a `base_url`. Strands defaults to Bedrock when no model is passed, and the official examples show the same class with a custom URL. The Zen gateway uses that interface.

```python
from strands.models.openai import OpenAIModel
vision = OpenAIModel(client_args={"api_key": key, "base_url": ZEN_URL}, model_id="deepseek-v4-flash-vision-exp",
                     params={"max_tokens": 2500, "temperature": 0})
```

The models are not Bedrock Claude models. Zen handled the photo and text paths, including demo photos taken in low indoor light and at an angle. Swapping a model provider is one constructor call, which is one reason Strands fit this build.

## Why the photos and case file stay local

Kindergarten paper may contain personal data. Two rules follow.

The photo is sent only for the vision call that transcribes it. The transcription, source crops, calendar file and reply draft stay with the case on local disk. `delete_case` removes the row, photo, crops and drafts, then vacuums SQLite. There is no soft delete.

The web page has no public upload route. Papelito does not use Funnel for the private page. The Devpost submission therefore omits a live demo URL.

Those two rules also draw the AgentCore boundary in the next section.

## AgentCore: what fits, and what does not

The AgentCore boundary follows one question: which parts of Papelito belong on Runtime, and which do not?

AgentCore Runtime is deployed in `eu-central-1`. The first green invoke, 2026-09-03, returned the synthetic seed title `Ausflug in den Tiergarten` (outing to the zoo), deadline `2026-09-07`, and `runtime: agentcore`. What follows is why the watchdog is still not on it.

**What fits.** Runtime hosts an agent behind an HTTP contract, `POST /invocations` and `GET /ping` on port 8080, ARM64. It is model-agnostic. The same `OpenAIModel` with a custom base URL runs there, and the gateway key goes into AgentCore Identity as an API-key credential. A Strands agent wraps in a few lines. The sidecar in `runtime/app/Papelito/main.py` is that wrap, pointed at Papelito extract and explain, not a chat agent.

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload, context):
    result = agent(payload.get("prompt", ""))
    return {"result": result.message}
```

The on-demand work maps onto that. Extract the actions, explain the card. Each is a request with an answer. The sidecar takes seed **text**, not an uploaded photo. Judges click a button on the PWA. The page calls Runtime with IAM SigV4. Photos stay on the local machine.

**What does not fit.** The watchdog. Three reasons, and none of them is that AgentCore is bad.

Runtime has no scheduler of its own. Scheduling it would add EventBridge Scheduler or another service, IAM work and retries to replace a two-line systemd timer.

Each session is an isolated microVM with ephemeral disk. The watchdog's whole job is to open `data/papelito.db`, find the cases due in two days, and write a due flag back. On Runtime the case file would have to move to DynamoDB or S3, and the photos and crops with it. At that point the rule from the previous section is gone and the product is a different product.

The local machine already has the case file and the clock. A daily timer on it does not need the network. The README says this plainly, and so does this post.

## The plan through judging

Judging runs from 15 September to 8 October 2026. Through that window the local machine keeps running the web page, timer and case file. The demo video shows the fake clock two days before a deadline, one run of `papelito watch`, and one English line.

The Runtime sidecar does two jobs: extract and explain. It receives the fixed, invented seed text from Kindergarten Sonnenblume and Fr. Huber. The PWA button invokes it without exposing an AWS console. The watchdog stays on systemd through judging.

The repo is public under MIT at https://github.com/robbyczgw-cla/papelito. The only pre-existing component is Web Search Plus MCP, published before the hackathon. Everything else was written in the submission period with help from AI coding assistants, as disclosed in the submission.

Next step: shoot the video. The sidecar is already live. Do not put an AWS console in the cut. Ten seconds of the seed-card button is enough.
