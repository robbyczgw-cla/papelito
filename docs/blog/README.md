# Blog posts for the Agents for Humans bonus

Three drafts for AWS Builder Center. Each published post counts 0.2 on the Stage Two score, capped at 0.6, so all three go up. Rules: https://agentsforhumans.devpost.com/rules (updated 2026-08-12).

| File | Job |
| --- | --- |
| `01-work-not-chat.md` | Why Papelito is a case file with a watchdog, not a scan-and-translate app |
| `02-strands-wiring.md` | The tools, the loop, the code. The "implementing" post |
| `03-aws-choices.md` | "Agents for Humans: AgentCore Runtime sidecar, watchdog stays on systemd" |

The first line of each file is the title. Then a blank line. Everything after it is the body.

## Deadline

Published and public on builder.aws.com before **Mon 2026-09-14 17:00 PDT** (Tue 2026-09-15 02:00 CEST). Moderation can take hours. Publish on Friday 11 Sep at the latest so a rejected post can be fixed and resubmitted.

Posts must stay public through judging, 15 Sep to 8 Oct 2026. Do not unpublish, rename, or move them.

## Publish

1. Sign in at https://builder.aws.com with the Builder Center account.
2. Click the "+" in the top bar, then "Create article".
3. Paste the first line of the file into the title field. Every title already contains "Agents for Humans". Keep it.
4. Paste the body into the editor. The editor takes markdown. Check that code blocks kept their fences and that the table in post 2 renders.
5. Post 2 has a mermaid block. If the preview shows raw text instead of a diagram, replace the block with the image at `docs/architecture.png` uploaded through the editor's image button.
6. Add tags if the form asks: `strands-agents`, `agents`, `python`, `agents-for-humans`.
7. Preview. Read the whole thing once on the phone-width preview.
8. Publish. The post waits for moderation and only counts once it is public.
9. Copy the public URL of each post into the Devpost submission form, "Blog posts" or the description field if there is no dedicated field.
10. Open each URL in a private browser window to confirm it is public.

The Devpost AWS Builder ID field takes the account email address, not the Builder Center alias.

## Before pasting

- Search each post for the repo link `https://github.com/robbyczgw-cla/papelito`. It appears once per post.
- Use only synthetic demo imagery and identities. Do not include private photos or personal details.
- Do not paste infrastructure identifiers into a post. Judges see the recorded Runtime call in the video; the hosted judge build has AgentCore disabled.
- Post 3 says Runtime is live in `eu-central-1` for extract and explain of request text. The recorded call uses preset demo text. Do not claim the watchdog runs there.

## Score

0.2 per post, three posts, 0.6 total. The bonus applies to the Stage Two score only.
