# Papelito

Kindergarten paper can combine an event, a cash payment and a deadline in a few lines of German. A parent who cannot skim the note may understand the translation but still miss what has to be done. With Papelito, the parent photographs the note once and reads an English card with what it is, what to do and by when. By then the calendar entry and the formal German reply already exist. Two days before the deadline, the synthetic demo reminder reads `In two days: 8 € for the outing, cash, Fr. Huber.` Papelito is built with Strands Agents. The agent reads the paper and opens a case; a daily watchdog checks its deadlines. Marking it done stops reminders; after the earliest active deadline passes, the watchdog asks once and closes the case.

## Inspiration

A small note can carry a payment, a Friday deadline and a request for rain boots. Translation alone does not put those actions into a calendar or reconcile the next slip.

## What it does

Photograph a note. Papelito reads it, pulls out every action with its deadline, and shows an English card with four columns: what, what to do, by when, done for you. While the parent reads, the agent writes the calendar entry with a 48-hour alarm and the German reply in Sie-form with approved profile names filled in. The parent copies the reply. Papelito never sends anything on its own.

Three things make it more than a scan.

A case, not a scan. One Kindergarten event is one case, and it lives across several pieces of paper. When the follow-up slip arrives, "moved to Friday, bring rain boots, confirm by tomorrow", the agent recognises it as an amendment to the open case. Papelito regenerates the calendar file, re-drafts the reply, moves the reminder, and shows the old items struck through.

It keeps working with the phone face down. A watchdog runs daily. For each open case with a deadline within two days and no reply marked sent, it writes an English reminder and flags the case as due in the web app. It reminds within the two-day window until you tap done. After the earliest active deadline passes, it asks once whether the reply was sent and closes the case. Reads once, acts for weeks. It never sends the reply.

The glossary covers Austrian Kindergarten terms, including MA (municipal department) and Gemeinde (municipality) on a letterhead, plus Hort (after-school care) and Elternverein (parents' association).

## How I built it

One Strands agent, plain Python tools decorated with `@tool`, and the agent loop deciding what to call. Zen's `deepseek-v4-flash-vision-exp` reads the photo and `deepseek-v4-flash` handles text through an OpenAI-compatible gateway. Everything after the photo is text: `extract_actions` returns each action with its German source sentence and a confidence, `resolve_dates` turns "bis Freitag" ("by Friday") into a date without a model call, `match_case` decides whether the actions amend an open case or start a new one, `write_ics` and `draft_reply` produce the two artifacts, `explain_in` writes the card in English.

`lookup_office` is a sub-agent. It finds what an office is and how to reach it through the Web Search Plus MCP server, attached with the Strands `MCPClient`, with identifiers stripped from the query first.

The case file is SQLite. The watchdog is `papelito watch` on a systemd timer. It finds due cases and writes the reminder. The mobile web page is a single FastAPI file for upload, the case list, mark done and delete.

The same extract and explain tools also run at a private Amazon Bedrock AgentCore Runtime endpoint in `eu-central-1`. Runtime accepts note text in the request; nothing is hardcoded into its entry point. The final video includes one recorded live call: a local PWA route sends a preset, invented German note stating that the outing is on 2026-09-09 and the 8 euro payment is due on 2026-09-07, then shows the returned card. Dead wait time in that clip is trimmed. The hosted judge build keeps AgentCore disabled. Photos, SQLite and the watchdog stay on the machine. Papelito never sends the reply.

## Challenges

Low-light, angled demo photos. The first thing the agent does is refuse a bad photo before spending a model call, and the second is to refuse to guess. A date extracted with low confidence keeps its German source line visible and asks one question. Below a threshold nothing is created. Every deadline on the card retains the German sentence it came from.

Deciding that a second note is the same event. That is a matching problem with fuzzy inputs on both sides, and getting it wrong means two calendar entries for one outing. `match_case` required the most iteration.

Not sounding like the dozen apps that already scan letters. The answer was to stop treating the card as the product and treat the reminder two days later as the product.

## Accomplishments

The watchdog demo: fake clock two days before the deadline, one run of `papelito watch`, exactly one English reminder. Tap done. Run again. Silence. That sequence is the second half of the video and the reason the project exists.

The amendment demo: the first synthetic photo plus a follow-up slip yield one case, one regenerated `.ics` file, and a formal German reply ready to copy.

## What I learned

The useful proof is the work after the first scan. The case stays open, the amendment updates it, and the watchdog writes one reminder, then goes silent once the case is marked done. The Strands loop handles the photo workflow as one agent using the same tools. The systemd watchdog handles the deterministic reminder separately.

## What's next

Keep the watchdog on systemd. Keep the AgentCore Runtime sidecar focused on extract and explain. The local PWA demo route invokes it only with fixed, invented note text; the hosted judge build keeps AgentCore disabled. Runtime itself accepts note text in the request. Uploaded photos and SQLite stay local.

## Disclosure

Written during the Submission Period with AI coding assistants (Grok, Claude, Codex). The only pre-existing component is Web Search Plus, an MCP server created before the hackathon and published on PyPI as `web-search-plus-mcp`. `lookup_office` uses it. Names, addresses and profile fields are stripped from the search query. Everything else is new.

## Built with

Strands Agents SDK, Python, SQLite, FastAPI, systemd, Web Search Plus MCP, OpenAI-compatible gateway, Amazon Bedrock AgentCore Runtime.

## Tagline field

The agent that reads the paper in your kid's schoolbag and does the work. Built with Strands Agents.

## Paste notes

Track: Everyday Agents.

Description: paste from `# Papelito` through the Built with list. Keep "built with Strands Agents" in paragraph one.

Repository: `https://github.com/robbyczgw-cla/papelito`

Architecture image: `docs/architecture.png`

Video: paste the public YouTube or Vimeo URL.

AWS Builder ID: use the account email address, not the Builder Center alias.

Live demo: `https://d3cknd2hkoyhzh.cloudfront.net`. Password-protected and preloaded with synthetic data only; use the supplied synthetic photos for uploads. Confirm who can view the testing-instructions field before putting credentials there. If it is public, supply them through another access-restricted channel.

Blog posts: paste the three public Builder Center URLs.
