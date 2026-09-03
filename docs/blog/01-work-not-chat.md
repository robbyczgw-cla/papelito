Agents for Humans: Papelito turns a Kindergarten slip into an open case

Austrian Kindergartens place paper in schoolbags. A typical week may bring a parent evening on the 17th, an outing with 8 € in cash due Monday, a closure day, or a request for a reply by Friday.

A parent who cannot skim German may translate the note but still miss the action or deadline. Papelito addresses that problem for the Everyday Agents track of Agents for Humans.

## The obvious thing is a translation app

Many apps photograph a German letter and explain it. They summarise, translate, draft a reply, and offer a tap to add a calendar entry. Then they stop. The Kindergarten does not stop.

Wednesday can bring a second slip. The synthetic German demo source reads: `Der Ausflug wurde auf Freitag verschoben. Regenstiefel nicht vergessen.` In English: "The outing has been moved to Friday. Don't forget rain boots." The earlier calendar entry is now wrong, and the copied reply is stale. A translation app can complete its task while leaving the parent with the wrong date.

The product is not only the card that explains the paper. Two days before the deadline, the demo reminder appears in English: `In two days: 8 € for the Ausflug, cash, Fr. Huber.` The parent never had to go back to the German slip.

## Three decisions that follow from that

**One event is one case, and a case lives across several pieces of paper.** When the Wednesday slip arrives, Papelito scores it against the open cases. Same sender, the word "Ausflug" (outing), a date within two weeks of the one on file, and the word "verschoben" (moved) in the text. It lands in the existing case as an amendment. The old Wednesday date is marked superseded and shows struck through. The calendar file, the German reply, and the reminder are marked stale and regenerated. The case preserves the earlier value so the parent can see what changed.

The reconciler required the most iteration. Getting it wrong means two calendar entries for one Ausflug, which is worse than no entry at all.

**The agent keeps working after the phone is face down.** A watchdog runs once a day from a systemd timer. For every open case with a deadline inside two days and no reply marked sent, it writes an English reminder and moves the case to the top of the list, marked due. It nags until the parent taps done. The next run is silent. Reads once, acts for weeks.

**Two artifacts in two languages from one photo.** The card is in English. The reply is in German, in Sie-form, with approved profile names filled in. The reply format changes with the sender type. Papelito never shows a translation without an action next to it.

## Two fixed rules

Papelito never sends anything. It drafts the reply for the parent to copy, writes a calendar file for the parent to open, and waits for the parent to mark the case done.

Papelito never invents a deadline. Every deadline on the card links back to the German sentence it came from. The synthetic source phrase `bis Freitag`, meaning "by Friday", resolves to a date in plain Python from the received date, with no model involved. If the model is not sure about a line, the card shows the crop of that line and asks one question. Below a threshold nothing is created and the line is listed as unreadable. Tests confirm that a daily schedule with only clock times does not become a calendar event.

## What the card looks like

Every photo becomes a card with four columns. The fourth column is the one that matters. This is synthetic demo output:

```
what                        do                              by when            done for you
Ausflug to the Tiergarten   8 € in cash in an envelope      Mon 07.09.2026     ✓ calendar entry, alarm Sat 05.09.
                            for Fr. Huber                   "bis Montag"       ✓ German reply drafted
                                                                               ✓ reminder Sat 05.09.
```

The by-when column quotes the German phrase the date came from, here `bis Montag`, "by Monday", next to the resolved date. The checkmarks in the last column appear one at a time as the tools run. Watching them fill in is the moment people understand the difference between this and a translation.

## Austrian terms matter

The glossary covers Austrian institutional terms and month names. The reply register changes with the sender. This is the difference between paper that gets answered and paper that gets a polite, wrong reply.

## How it is built, briefly

Papelito is one agent built with Strands Agents and a list of plain Python tools. The agent loop picks the next tool. A vision model reads the photo. Everything after that is text and SQLite on a local machine. The photo is sent only for the vision call. FastAPI serves the mobile web page locally. The code is public under MIT at https://github.com/robbyczgw-cla/papelito. The second post in this series walks through the tools. The third covers the live AgentCore Runtime sidecar and why the watchdog stays on systemd.

## What the build showed

The card alone looks like a translation feature. The watchdog proves the longer workflow: set the test clock two days before the deadline, print one English reminder, mark the case done, and run it again. The second run is silent.

Next step: record the demo and end on the architecture after the watchdog goes silent.
