# Papelito demo video

Shooting script. English voiceover. No music.

Devpost: **"Demo video (maximum 5 minutes)"**. That is a ceiling, not a target. Presentation scoring is whether the video shows the project working end-to-end and pitches problem / who / why. A 5:00 cut padded with architecture is worse than a tight ~3:00.

**Target cut 2:50. Do not pad to 5:00.** Slack only if a tool is slow. If you still have time, extend the silent hold after the second watchdog run. Do not add a third language, a settings tour, or a chat.

The ping is the product. The card is the receipt. Open on the face-down phone. End on the architecture after the done-and-silence proof.

## Specs

- One speaker, plain English, conversational. Not a trailer voice.
- Room tone only. No bed, no whoosh, no keyboard SFX under the tools.
- Burn-in captions for every German line on screen. Do not caption English UI or the English voiceover.
- Tool names as a monospace ticker the frame they fire. Leave each name up until the next one.
- Demo profile on screen: Lucía García, Mateo, Kindergarten Sonnenblume. These are invented names. Use only `photos/demo/` and the fictional slips below.
- Title cards for time jumps only: `Earlier that week` · `Wednesday` · `Two days before`.
- Ping source: the `.ics` VALARM (Apple or Google Calendar, 48 hours before) and/or the English due line. Do not fake a push notification the product does not send.
- Never hit send. Copy the reply, stop.
- Diagram: `docs/architecture.png`, final 10 seconds.

Say **Strands Agents** once, in beat 1, in the sentence below. Do not list tools in that sentence. Do not say it again over the diagram.

## Do not

- Open on the diagram, a language picker, or a chat transcript.
- Name another product.
- Say a named office, institution, legal dispute, or city.
- Demo more than one reader language. English is the reader language. German is the institution language.
- Show an AWS console.
- Put music under the silence after `papelito done`.

## Runtime (2:50)

| Time    | Beat                                      |
| ------- | ----------------------------------------- |
| 0:00    | Phone face down, ping                     |
| 0:25    | Photo, tools, fourth column               |
| 1:05    | Open calendar, copy reply                 |
| 1:30    | Follow-up slip, amendment                 |
| 2:05    | `python -m papelito.watch --today`, one reminder, `papelito done`, silence |
| 2:40    | Architecture, 10 seconds                  |
| 2:50    | End                                       |

Shoot to this table. Cut voice until each beat fits.

---

## 0:00-0:25  Phone face down.

**Picture.** Neutral tabletop, phone face down. Two seconds of room tone. A ping. Do not flip the phone. Super the clearly labelled English demo line over the phone. Hold. Cut to black. Cut to the synthetic Kindergarten slip coming out of a schoolbag.

**Voice.** Keep it under 50 words. Stop for the ping.

> Kindergarten paper arrives in German: eight euros in an envelope by Monday. A parent may understand the words and still miss the work.
>
> *(ping. hold.)*
>
> The phone is down. The work still happens. Papelito is an agent built with Strands Agents. It reads the slip, opens a case, and keeps working.

**On screen.**

| Kind    | Text |
| ------- | ---- |
| Burn-in | In two days: 8 € for the Ausflug, cash, Fr. Huber. |
| Source  | `In two days: 8 € for the Ausflug, cash, Fr. Huber.` |
| Paper   | Leave the German unread. Caption it in beat 2 when it is photographed. |
| Tools   | None. |

**Cut.** Title card: `Earlier that week`.

---

## 0:25-1:05  Photo. Tools. Fourth column.

**Picture.** Papelito is open in English on the phone. The demo parent photographs the slip from `photos/demo/` or uploads it. Tool ticker along the bottom. The card builds in four columns. Watch the fourth column. Checkmarks appear as the tools return, not before. Hold on the finished card long enough to read the burn-ins.

**Paper in frame (print this).**

```
Kindergarten Sonnenblume
Ausflug in den Tiergarten am Mittwoch.
Bitte 8 € bis Montag in einem beschrifteten Kuvert mitgeben, an Fr. Huber.
```

**Voice.** Talk, then shut up so the ticker can work.

> The demo parent photographs it once.
>
> *(tools run, no voice)*
>
> Four columns: what, what to do, by when, done for you. The fourth column is the work already finished while the parent reads.

**On screen, in order.**

Ticker: `check_photo` → `read_note` → `extract_actions` → `resolve_dates` → `match_case` → `save_case` → `explain_in` → `write_ics` → `draft_reply`

| Kind    | Text |
| ------- | ---- |
| Burn-in | Outing to the zoo (Tiergarten). |
| Source  | `Ausflug in den Tiergarten` |
| Burn-in | 8 € cash in an envelope for Fr. Huber. |
| Source  | `Bitte 8 € bis Montag in einem beschrifteten Kuvert mitgeben.` |
| Burn-in | Mon 7 Sep 2026, from "by Monday". |
| Source  | `"bis Montag"` |
| Burn-in | Calendar event, alarm Sat 5 Sep. |
| Source  | `✓ calendar event, alarm Sat 05.09.` |
| Burn-in | German reply ready. |
| Source  | `✓ German reply ready` |
| Burn-in | Reminder Sat 5 Sep. |
| Source  | `✓ reminder Sat 05.09.` |

Keep the column headers in English: `what` · `what to do` · `by when` · `done for you`.

Tap the deadline so the German crop is visible. Caption that crop: `Please send 8 € by Monday in a labelled envelope.` Source: `Bitte 8 € bis Montag in einem beschrifteten Kuvert mitgeben.`

---

## 1:05-1:30  Calendar. Copy reply. Do not send.

**Picture.** Tap open calendar. Cut to Apple Calendar or Google Calendar with the imported event **and** the 48-hour alarm, not a date chip on the card. Alarm on Saturday 5 Sep for the Monday envelope. Back to Papelito. Tap copy reply. The German letter fills the frame. Synthetic demo names from the profile: Mateo in the body, Lucía García on the signature. Toast: copied. Do not paste it into Mail. Do not hit send.

**Voice.**

> Open calendar. The event is there, with an alarm two days before.
>
> Copy reply. Formal German, demo profile names already filled in. The parent decides whether to send it. Papelito never does.

**On screen.**

Ticker: `write_ics` if it is still on the card; `draft_reply` as the letter appears.

| Kind    | Text |
| ------- | ---- |
| Burn-in | Dear Mrs Huber, |
| Source  | `Sehr geehrte Frau Huber,` |
| Burn-in | I confirm Mateo will attend the outing to the zoo. I will send the 8 euros on Monday in a labelled envelope. |
| Source  | `hiermit bestätige ich die Teilnahme von Mateo am Ausflug in den Tiergarten. Die 8 Euro gebe ich am Montag in einem beschrifteten Kuvert mit.` |
| Burn-in | Kind regards, Lucía García |
| Source  | `Mit freundlichen Grüßen` / `Lucía García` |

Calendar event title in German stays German. Caption it: `Outing, 8 €, envelope for Fr. Huber.`

---

## 1:30-2:05  Wednesday. Amendment.

**Picture.** Title card: `Wednesday`. A second slip on the table. Photograph it in the same page, same case list. `match_case` is the ticker that matters. One case, not two. Old Wednesday line struck through. New Friday date. Rain boots on the card. Reply re-drafted. Reminder moved. Paper count on the slip: two papers.

**Paper in frame (print this).**

```
Der Ausflug wurde auf Freitag verschoben.
Gummistiefel mitgeben.
Rückmeldung bis morgen.
```

**Voice.**

> Wednesday. They moved it to Friday, rain boots, confirm by tomorrow.
>
> Same case. Old date struck through. Calendar replaced. Reply rewritten. Reminder moved.

**On screen.**

Ticker: `check_photo` → `read_note` → `extract_actions` → `resolve_dates` → **`match_case`** (hold this one) → `save_case` → `explain_in` → `write_ics` → `draft_reply`

| Kind    | Text |
| ------- | ---- |
| Burn-in | Moved to Friday. Bring rain boots. Confirm by tomorrow. |
| Source  | `auf Freitag verschoben, Gummistiefel mitgeben, Rückmeldung bis morgen` |
| Burn-in | Outing on Wednesday *(struck through)* |
| Source  | the superseded row, old date visible |
| Burn-in | Outing on Friday. |
| Source  | the new row |
| Burn-in | Thanks for the note on the Friday outing. The 8 euros go Monday in a labelled envelope, rain boots too. |
| Source  | `danke für die Information zum Ausflug am Freitag. Der Betrag von 8,- Euro wird am Montag in einem beschrifteten Kuvert mitgegeben, die Regenstiefel ebenso.` |

If the card says the row was updated from a later note, caption that too.

---

## 2:05-2:40  Watch once. One reminder. Done. Silence.

**Picture.** Split or cut between a large terminal and the synthetic case list. Title card: `Two days before`. Fake clock. Run watch once. Exactly one English line appears in the terminal. The Ausflug case jumps to the top, marked due. The Elternabend case does not move. Run `papelito done` with the id on screen. Run watch again with the same `--today`. Empty stdout. The due badge is gone. Hold the empty terminal for two full seconds. Do not fill them.

**Terminal (large font, one command at a time).**

```bash
uv run python -m papelito.watch --today 2026-09-10
```

Stdout, one line:

```
In two days: 8 € for the Ausflug, cash, Fr. Huber.
```

Ticker while it runs: `list_open` → `mark_due`

The case turns due at the top of the list. Same English line on the card.

```bash
uv run papelito done ausflug
```

Use the real case id from the list. Then:

```bash
uv run python -m papelito.watch --today 2026-09-10
```

Stdout: nothing. Cursor blinks.

**Voice.**

> Two days before the deadline, the daily watchdog writes one reminder in English. One case. One line.
>
> The demo parent taps done after sending the envelope.
>
> Watch again.
>
> *(no voice through the empty output)*

**On screen.**

| Kind    | Text |
| ------- | ---- |
| Burn-in | In two days: 8 € for the Ausflug, cash, Fr. Huber. |
| Source  | `In two days: 8 € for the Ausflug, cash, Fr. Huber.` |

Keep the due badge in English. Do not caption the empty second run. The point is nothing to read.

Do not run the after-deadline question in this video. One nag, then done, then silence.

---

## 2:40-2:50  Architecture, final 10 seconds.

**Picture.** Full frame `docs/architecture.png`. No zoom-out from a laptop. Highlight the local path, then the AgentCore Runtime sidecar. Keep this image on screen through the end.

**Voice.** Do not say Strands Agents again. Two short sentences, no more than 25 words.

> The local tools write the card, calendar, reply, and SQLite case. AgentCore handles seed-text extract and explain; the daily watchdog stays on systemd.

**On screen.** Tool names are the labels on the diagram. No extra ticker.

---

## Optional 10-second AgentCore insert

Omit this from the 2:50 cut unless the Runtime response is clean and fast. If included, place it before the architecture, shift the architecture to 2:50-3:00, and end at 3:00. The architecture must remain the final 10 seconds.

**Picture.** On the PWA seed card, tap `Run on AgentCore`. Show the returned card for the fixed Ausflug seed text. Keep any question on the card. Do not show an AWS console, a request inspector, or infrastructure identifiers.

**Voice.** Optional: `The same extract and explain path also runs on AgentCore Runtime with invented seed text.`

---

## Caption sheet

Burn these. If a line is not on screen, skip it. English on the lower third. Keep the original visible in the UI.

| Timecode | Original | Burn-in |
| -------- | -------- | ------- |
| 0:12 | In two days: 8 € for the Ausflug, cash, Fr. Huber. | In two days: 8 € for the Ausflug, cash, Fr. Huber. |
| 0:30 | Ausflug in den Tiergarten am Mittwoch. Bitte 8 € bis Montag in einem beschrifteten Kuvert mitgeben, an Fr. Huber. | Outing to the zoo on Wednesday. Please send 8 € by Monday in a labelled envelope, to Fr. Huber. |
| 0:45 | what / what to do / by when / done for you | what / what to do / by when / done for you |
| 0:48 | Ausflug in den Tiergarten | Outing to the zoo (Tiergarten). |
| 0:50 | Bitte 8 € bis Montag in einem beschrifteten Kuvert mitgeben. | 8 € cash in an envelope for Fr. Huber. |
| 0:52 | "bis Montag" | Mon 7 Sep 2026, from "by Monday". |
| 0:55 | ✓ calendar event, alarm Sat 05.09. | Calendar event, alarm Sat 5 Sep. |
| 0:57 | ✓ German reply ready | German reply ready. |
| 0:59 | ✓ reminder Sat 05.09. | Reminder Sat 5 Sep. |
| 1:08 | (calendar event title, German) | Outing, 8 €, envelope for Fr. Huber. |
| 1:17 | Sehr geehrte Frau Huber, | Dear Mrs Huber, |
| 1:19 | hiermit bestätige ich die Teilnahme von Mateo am Ausflug in den Tiergarten. Die 8 Euro gebe ich am Montag in einem beschrifteten Kuvert mit. | I confirm Mateo will attend the outing to the zoo. I will send the 8 euros on Monday in a labelled envelope. |
| 1:25 | Mit freundlichen Grüßen / Lucía García | Kind regards, Lucía García |
| 1:35 | auf Freitag verschoben, Gummistiefel mitgeben, Rückmeldung bis morgen | Moved to Friday. Bring rain boots. Confirm by tomorrow. |
| 1:50 | (struck-through Wednesday row) | Outing on Wednesday. |
| 1:53 | (new Friday row) | Outing on Friday. |
| 1:58 | danke für die Information zum Ausflug am Freitag. Der Betrag von 8,- Euro wird am Montag in einem beschrifteten Kuvert mitgegeben, die Regenstiefel ebenso. | Thanks for the note on the Friday outing. The 8 euros go Monday in a labelled envelope, rain boots too. |
| 2:15 | In two days: 8 € for the Ausflug, cash, Fr. Huber. | In two days: 8 € for the Ausflug, cash, Fr. Huber. |

---

## Tool ticker

Show the identifier only. No gloss.

First photo: `check_photo` `read_note` `extract_actions` `resolve_dates` `match_case` `save_case` `explain_in` `write_ics` `draft_reply`

Amendment: same list, hold `match_case`.

Watch: `list_open` `mark_due`

---

## Shoot notes

- Reset the PWA with `POST /api/demo/seed` before the first take.
- Use only `photos/demo/` and the two fictional slips above. Never use personal photos.
- Print both slips. Use soft indoor light and a slight angle. Do not use a perfect scan.
- Record the web app at phone size. Record the terminal at laptop size. Do not show the card in a small terminal window.
- If a tool is slow, keep rolling. The cap is 5:00. Cut room tone, not the ticker.
- Before recording the watchdog take, verify that `--today 2026-09-10` prints exactly one reminder for the synthetic Ausflug case due on 2026-09-12.
- Rehearse the second watch until stdout is empty. That hold is the cut.
- Voiceover after picture lock. Leave holes for the tools and for the empty watch.
