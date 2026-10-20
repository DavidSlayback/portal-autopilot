# Demo emails

Sends the two notification emails from section 5 of [bot/SETUP.md](../bot/SETUP.md) to the
inbox the Sentry Bot watches, instead of sending Gmail drafts by hand. Use them in demo
order: the phish first (story 0), then the real statement (stories 1–3).

## Set up once

1. On the Gmail account the Bot watches, turn on 2-Step Verification and create an
   [app password](https://myaccount.google.com/apppasswords).
2. `cp demo-emails/.env.example demo-emails/.env` and fill in that address and app password.
3. That address must be in the `bluebonnet` entry's `senders` in `~/autopilot/portals.json`
   on the Bot computer (SETUP.md step 1).

## Send

```sh
uv run demo-emails/send.py both --dry-run   # check the messages first
uv run demo-emails/send.py phish            # expected: quarantine
uv run demo-emails/send.py trusted          # expected: trusted, handed to Clerk
```

The phish is quarantined because a registered Bluebonnet sender claims to be Cedar Hollow, the
link text and target differ, and the target imitates the bank's domain.
