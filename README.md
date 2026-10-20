# Portal Autopilot

Every "you have a new message, log in to view" email, handled: a Grok Bot vets the email
without clicking it, logs into the real portal, files the document, puts deadlines on your
calendar, and catches bills you don't owe by comparing documents across portals.

- **Sentry Bot** checks each notification with `autopilot gate`: registered sender,
  SPF/DKIM/DMARC, link domains, look-alike and punycode domains, mismatched link text. It never
  opens the emailed link.
- **Clerk Bot** opens the portal's *registered* URL using its saved login, extracts statements,
  claims and messages, then runs `autopilot reconcile`, which compares provider bills against
  insurer EOBs by claim number. It drafts disputes and appeals and sends them only after you
  approve.

Decisions are deterministic Python; the Bot does the reading and clicking.

## Use

```sh
uv tool install git+https://github.com/DavidSlayback/portal-autopilot
autopilot gate examples/email_phish.json            # quarantine, with reasons
autopilot reconcile examples/records.json --format md
```

Bot instructions, routines and the pre-flight checklist are in [bot/SETUP.md](bot/SETUP.md).
User stories with status and owners are in [STORIES.md](STORIES.md).
The staged portals (fictional hospital, insurer and bank) are served from `docs/` at
https://davidslayback.github.io/portal-autopilot/.

## Develop

```sh
uv run --group dev pytest
```
