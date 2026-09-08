# Papelito usability test guide

Facilitator copy for hackathon demo testing.

## 1. Purpose

Papelito is an English-language demo. A user uploads a photo of a paper note from an Austrian kindergarten. The system produces:

- an English action card showing what to do, by when, how much to pay, and where that information appears in the note;
- a downloadable calendar file with an alarm 48 hours before the deadline;
- a formal German reply that the user can copy. The system never sends the reply.

A second note can amend an existing case. The system does not invent deadlines and should show when it is unsure.

This test checks whether parents with no prior explanation can:

1. understand what the product is for;
2. upload a note and find the deadline, amount, and source for each;
3. understand what an amendment changed;
4. download the calendar file and copy the German reply without trying to send it;
5. describe what they expect when a note is unclear.

This is a formative test. It looks for confusion and errors, not for a score.

## 2. Participants and safety rules

### Participants

- Two or three parents or guardians of children of kindergarten or primary-school age.
- German knowledge is not required; non-German speakers are the primary audience.
- No previous exposure to Papelito.
- One participant at a time, 15 minutes each, with a five-minute buffer between sessions.

### Materials

- A laptop or tablet with a browser. The shared judge demo is at `https://d3cknd2hkoyhzh.cloudfront.net`. It is password-protected, and credentials are provided separately. Never show, read aloud, or write credentials in the test notes.
- These two synthetic demo files, already on the test device:
  - `photos/demo/01-ausflug.png` (first note; *Ausflug* means "outing")
  - `photos/demo/02-ausflug-nachtrag.png` (amendment; *Nachtrag* means "addendum")
- This guide, a timer, the results table, and the issue log.

### Prepare a clean test case

The hosted judge demo is shared and may already show the amended case. Do not delete or reset any case on that shared deployment.

For measured sessions, ask a team member to provide a separate disposable test instance or empty test database for each participant. Before the participant sits down:

1. Confirm that the participant's instance shows no existing Papelito cases.
2. Configure the first upload of `photos/demo/01-ausflug.png` with `received_on` set to `2026-09-03`.
3. Configure the later upload of `photos/demo/02-ausflug-nachtrag.png` with `received_on` set to `2026-09-08`.
4. Open the participant's isolated instance at its start screen without uploading either note.

If you cannot provide an empty instance and those two exact received dates without changing shared data, do not run a measured session. You may use the shared judge demo for an unscored walkthrough, but do not enter that walkthrough in the results table.

### Rules

- Use only the two synthetic files above. Do not upload real notes, real photos, or anything containing a real child's or teacher's name.
- Copy the German reply only. Nobody pastes it into an email, messenger, or form during the session. Say this aloud before Task 4.
- Do not enter or show the demo password in front of the participant. If the session logs out, pause the timer, enter the password out of view, and resume.
- Ask for verbal consent before taking notes or recording the screen. Do not record a face or voice unless the participant explicitly agrees. Participants may stop at any time.
- Do not help unless the participant is stuck for more than 60 seconds or asks for help. Record every intervention.
- Do not explain how the product works before or during the tasks. Answer questions after the post-test questions.

## 3. Schedule: 15 minutes

| Time | Block | Content |
|---|---|---|
| 0:00 to 1:30 | Introduction | Welcome, consent, rules, think-aloud instruction |
| 1:30 to 3:00 | Task 1 | Problem understanding, with no interaction yet |
| 3:00 to 6:30 | Task 2 | Upload first note; find deadline, amount, and source |
| 6:30 to 8:30 | Task 3 | Upload amendment; explain what changed |
| 8:30 to 11:00 | Task 4 | Calendar file and German reply; never send |
| 11:00 to 12:30 | Interview prompt | Discuss uncertainty expectations; do not score product behavior |
| 12:30 to 15:00 | Wrap-up | Post-test questions and thanks |

If Task 2 is not finished by 7:00, move on and record it as "not completed."

## 4. Facilitator script

Read the quoted parts as written. Keep your tone neutral. Do not react to success or failure.

### Introduction: 0:00

> Thanks for helping. We are testing an early demo, not you. Nothing you do here is wrong. If something is confusing, that is useful for us.
>
> I will give you small tasks. Please say aloud what you are thinking and what you expect to happen. I will mostly stay quiet. If you are stuck, try for a moment first; I will help if needed.
>
> Everything on the screen is made up. There are no real children, teachers, or families in these documents.
>
> Is it okay if I take notes and record the screen? You can stop at any time.

Wait for consent, then start the timer.

### Task 1: problem understanding at 1:30

Show the demo start screen. Do not click anything.

> Before we start: looking at this screen, what do you think this is for? Who would use it, and when?

Then show `01-ausflug.png` on screen or as a printout.

> This is a note a kindergarten might hand out. Imagine you found it in your child's bag. What would you want to know from it?

Do not translate the note. Record whether the participant mentions a deadline, money, or a reply.

### Task 2: first note at 3:00

> Please use this program to find out what you need to do. The picture is already saved on this computer as `01-ausflug.png`. Go ahead.

When the result appears, ask:

> By when do you have to do something? How much money is involved? How do you know the program got this from the note rather than making it up?

Record the time from upload to each correct answer. Record whether the participant finds the source information without help.

### Task 3: amendment at 6:30

> A few days later, the kindergarten sends a second note about the same outing. The file is called `02-ausflug-nachtrag.png`. Please add it and tell me what changed compared with the first note.

Do not say what changed. Record whether the participant identifies the change from the screen and understands that both notes belong to the same case.

### Task 4: calendar and reply at 8:30

> Two things. First, get a reminder for this into your calendar. Second, the kindergarten wants a short written answer in German. Please get that answer ready to copy.
>
> Important: do not send anything. Do not paste the text into an email or message. We only want to see that you can copy it.

Record whether the participant finds the calendar download, understands that the reminder is 48 hours before the deadline, finds the copy function, and tries to send or paste the reply anywhere.

If the participant asks whether the German is correct, answer:

> We are not testing your German today. What do you expect this text to be, and who would it go to?

If the participant reads German, you may point to the salutation to check whether they recognise it as formal, for example *Sehr geehrte Frau ...* ("Dear Ms ...," in a formal register). Do not comment on the rest of the text.

### Interview prompt: uncertainty expectations at 11:00

This is a discussion prompt, not a measured product test. Do not upload anything and do not mark it pass or fail.

> Imagine a note that says a trip is "sometime next week" and does not give a day or a price. What would you expect this program to show you? What would you not want it to do?

Record the participant's expectations as interview notes only. Do not treat the answer as evidence of current product behavior.

### Wrap-up at 12:30

Ask the post-test questions in section 7. Then say:

> That's all. Thank you. Is there anything you would like to ask me about what you saw?

Answer questions now and stop any recording.

## 5. Success criteria

A task passes only if all its criteria are met without facilitator help. Record partial results in the table.

| Task | Criteria |
|---|---|
| 1 | The participant names at least one relevant need: action, deadline, payment, or reply. They describe the product as help with kindergarten or school paperwork. |
| 2 | Upload completed within 90 seconds. Correct deadline stated within 60 seconds of the result appearing. Correct amount stated within 60 seconds. Participant points to the source information when asked. |
| 3 | The second file is added and appears in the same case. The participant states what changed and which value now applies, matching the screen. |
| 4 | Calendar file downloaded. Participant states that the alarm is 48 hours before the deadline. Reply copied. Participant does not try to send, paste, or share it and can state that Papelito does not send anything. |

For each task, record pass, partial, or fail; completion time; and the number of facilitator interventions.

## 6. Observations to record

- Where the participant hesitates for more than five seconds and what they are looking at.
- Wrong clicks or paths and whether they recover without help.
- Words the participant uses that differ from the interface labels.
- Whether they read or ignore the German reply.
- Whether they trust the deadline and amount immediately or check them against the note.
- Whether they notice the source reference before being asked.
- Whether they realise that the second note replaced or added information.
- Any attempt to send, share, or paste the reply.
- Anything they expected to see but did not.
- Technical problems: slow loading, upload failure, exact error messages, or logout.

Record what happened, not your interpretation. Interpret the observations after the sessions.

## 7. Post-test questions

Ask every participant the same questions in the same order. Do not lead.

1. In your own words, what does this program do?
2. What did you find hardest?
3. What would you check before trusting the deadline it showed you?
4. What happened when you added the second note? Was that what you expected?
5. What do you think happens to the German text after you copy it?
6. If the program was unsure about a date or amount, how would you want it to tell you?
7. Is there anything you expected to do here but could not?
8. Would you use this for a real note from your kindergarten or school? Why or why not?

Write answers as close to the participant's words as possible.

## 8. Results table

Use participant codes P1, P2, and P3 only. Do not record names.

| Item | P1 | P2 | P3 |
|---|---|---|---|
| Date and time | | | |
| Reads German: yes, some, or no | | | |
| Consent to notes or screen recording | | | |
| Task 1: pass, partial, or fail | | | |
| Task 2: pass, partial, or fail | | | |
| Task 2: time to upload, seconds | | | |
| Task 2: time to correct deadline, seconds | | | |
| Task 2: time to correct amount, seconds | | | |
| Task 2: source found without help, yes or no | | | |
| Task 3: pass, partial, or fail | | | |
| Task 3: change described correctly, yes or no | | | |
| Task 4: pass, partial, or fail | | | |
| Task 4: calendar file downloaded, yes or no | | | |
| Task 4: 48-hour alarm understood, yes or no | | | |
| Task 4: reply copied, yes or no | | | |
| Task 4: attempted to send or paste, yes or no | | | |
| Uncertainty discussion notes | | | |
| Facilitator interventions, count | | | |
| Session ended early, with reason | | | |

## 9. Issue log

Use one row per observed problem. Number issues consecutively across all participants.

| # | Participant | Task | What happened: facts only | Severity | Repeated? |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |
| 6 | | | | | |

Severity:

- **Blocker:** The task could not be completed without help.
- **Major:** The task was completed with a wrong result, a wrong assumption, or more than 60 seconds lost.
- **Minor:** The participant hesitated, expected a different label, or encountered a cosmetic issue.

Complete "Repeated?" after all sessions. Enter yes if the same issue appeared for more than one participant.

## 10. Stop conditions

Stop the current session and record the reason if:

- the participant asks to stop or shows discomfort;
- the participant tries to upload a real document or a photo of a real person;
- the participant tries to send the German reply to a real address or account;
- the demo is unreachable or an error cannot be cleared within two minutes;
- the demo asks for the password in view of the participant and it cannot be entered privately;
- the session exceeds 20 minutes.

Stop the entire test round and report the issue if:

- the same blocker appears for two participants in a row;
- a result contains a deadline or amount that does not appear in the synthetic note;
- any real personal data appears on screen.

After stopping, fill in everything observed and mark the remaining items "not run."
