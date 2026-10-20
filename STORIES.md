# User stories

Everything happens in one loop: a "log in to view" email arrives, Sentry vets it, Clerk logs into the
registered portal, files what it finds, compares documents across portals, and drafts the fix.
Bot prompts and setup steps are in [bot/SETUP.md](bot/SETUP.md).

**Status:** `done` = built and tested locally · `prompt` = Bot instructions written, not yet run
in Grok Bot · `todo` = not started. Put your name in **Owner** when you take one.

## People

- **Alex**: has a dozen login-only portals (MyChart, insurer, bank, utilities, landlord).
- **Sam**: a one-person founder with government, payroll, bank and vendor portals.
- **Other agents**: Claude Code or other Bots that need what is behind those logins.

## Must (the demo)

| # | Story | Done when | Status | Owner |
|---|---|---|---|---|
| 0 | **Gatekeeper.** As Alex, every "log in to view" email is checked without anyone clicking its link. | A real MyChart email returns `trusted: mychart`. A look-alike bank email is quarantined, its reasons are messaged to Alex, and nothing opens the link. | Code `done` (`autopilot gate`). Sentry Bot `prompt`. | |
| 1 | **Notification → document.** As Alex, a trusted notification gets the actual message or document filed for me. | Clerk opens the **registered** portal URL (never the emailed link), and the document lands in Drive `Portals/<portal>/` within ~2 minutes. | `prompt` | |
| 2 | **One-line meaning.** As Alex, I get one sentence saying what it is and whether I need to act. | Each item gets one line: what it is, the amount, and the action (none, pay by, dispute by, or appeal by). | Summary `done` (`reconcile` output). Bot message `prompt`. | |
| 3 | **Deadlines on my calendar.** As Alex, any date I must act by appears on my calendar. | A Calendar event on the finding's `deadline`, with the amount and a Drive link. | `prompt` | |
| 4 | **Catch money I don't owe.** As Alex, when a provider bill doesn't match my insurer's EOB, I'm told the difference and why. | Bill and EOB are matched by claim number in code, not by the model. The demo data shows **$372 overbilled**, one denied claim to appeal, and one bill never sent to insurance. | `done` (`autopilot reconcile`, tested) | |
| 7 | **Log in once.** As Alex, I sign in to each portal once, including 2FA, and never again. | MyChart is signed in through the takeover flow (the Bot never sees the password). A second run needs no human. | `todo` | |

## Should (the ambitious part)

| # | Story | Done when | Status | Owner |
|---|---|---|---|---|
| 5 | **Draft the fix, send on approval.** As Alex, the Bot drafts the dispute or appeal and sends it only after I approve. | The letter is shown and approval requested. After approval it is sent through the hospital portal's message form, and the confirmation number is filed. | Letters `done` (`letters.py`), portal form `done`, approval step `prompt` | |
| 5b | **Wrong autopay.** As Alex, I'm told when a scheduled bank payment pays a bill I shouldn't pay in full. | The bank's $412 autopay to Bluebonnet is flagged: "you owe $40, edit before 11/13." The Bot does not change the payment itself. | `prompt` | |
| 6 | **Check portals that never email.** As Sam, a nightly routine checks every registered portal and reports only what's new. | A 7:00 AM routine. An unchanged portal produces no message, because memory tracks what has been seen. | `prompt` | |

## Stretch

| # | Story | Done when | Status | Owner |
|---|---|---|---|---|
| 8 | **Feed for other agents.** As Claude Code, I can read every document, amount and deadline without logging in anywhere. | Clerk writes `ledger.json` to Drive after each run, and another agent answers "what's due this week?" from it. | `todo` | |
| 9 | **Learn a new portal from one email.** As Alex, I forward a notification from a portal the Bot has never seen, and it learns that portal. | The Bot finds the login and the documents, then saves them as a skill and a registry entry for me to confirm. Pre-recorded only; too risky to run live. | `todo` | |
| 10 | **Ignore instructions inside documents.** As Alex, text inside a portal message never makes the Bot act. | A planted "remit to new account" message is reported as suspicious and nothing happens. | Mostly covered by 0 and Clerk's rules. `todo` to plant and test. | |

## Demo order (about 3 minutes)

1. Send the phish (story 0): it is quarantined live, and the reasons appear.
2. Send the real or staged statement email: Clerk files the document and the calendar event appears (stories 1–3).
3. The summary reports $372 overbilled, the wrong autopay, a denied MRI and a bill never sent to insurance (stories 4 and 5b).
4. Approve the dispute: the confirmation appears in the hospital portal (story 5).
5. Show the nightly routine and the MyChart session that is already signed in (stories 6 and 7).

## Pre-flight before judging (8:30)

- [ ] The real MyChart email passes the gate with no false flags.
- [ ] Clerk has completed one full run on the staged portals.
- [ ] A backup screen recording of the full run exists.
- [ ] The hospital's sent messages are reset (clear site data for `davidslayback.github.io`).
