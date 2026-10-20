"""Send the two demo notification emails to the inbox the Sentry Bot watches.

    uv run demo-emails/send.py phish            # story 0: should be quarantined
    uv run demo-emails/send.py trusted          # stories 1-3: should reach Clerk
    uv run demo-emails/send.py both --dry-run   # print the messages, send nothing

Both come from the one Gmail address registered as Bluebonnet's sender (by default the
watched inbox, sending to itself), as in section 5 of bot/SETUP.md. The address and app
password come from demo-emails/.env (git-ignored), never from this file.
"""
import argparse
import os
import smtplib
import sys
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

HOSPITAL_URL = "https://davidslayback.github.io/portal-autopilot/hospital/"

EMAILS = {
    "trusted": {
        "display_name": "Bluebonnet Patient Billing",
        "subject": "Bluebonnet Regional: you have a new statement. Log in to view.",
        "text": "You have a new statement from Bluebonnet Regional Medical Center.\n"
                "For your privacy, we don't include statement details in email.\n\n"
                f"Log in to view: {HOSPITAL_URL}\n",
        "html": "<p>You have a new statement from Bluebonnet Regional Medical Center.</p>"
                "<p>For your privacy, we don't include statement details in email.</p>"
                f'<p><a href="{HOSPITAL_URL}">Log in to view</a></p>',
    },
    "phish": {
        "display_name": "Cedar Hollow CU Secure Message",
        "subject": "Cedar Hollow CU: new secure message. Verify your account to avoid suspension",
        "text": "You have 1 new secure message. Action required within 24 hours or your "
                "account will be suspended.\n\nView message: cedarhollowcu.example/secure\n",
        # The visible text and the real target differ on purpose. The target is a reserved,
        # unresolvable .example domain, and the Bot must never open it.
        "html": "<p>You have 1 new secure message. <b>Action required within 24 hours</b> "
                "or your account will be suspended.</p>"
                '<p><a href="https://cedarhollow-cu-secure.example/login">cedarhollowcu.example/secure</a></p>',
    },
}


def load_env(path):
    """Read KEY=value lines into os.environ without overriding what is already set."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build(kind, sender, to):
    spec = EMAILS[kind]
    msg = EmailMessage()
    msg["From"] = formataddr((spec["display_name"], sender))
    msg["To"] = to
    msg["Subject"] = spec["subject"]
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1])
    msg.set_content(spec["text"])
    msg.add_alternative(spec["html"], subtype="html")
    return msg


def need(name):
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Missing {name}. Copy demo-emails/.env.example to demo-emails/.env and fill it in.")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("which", choices=["trusted", "phish", "both"])
    parser.add_argument("--dry-run", action="store_true", help="print the messages instead of sending")
    args = parser.parse_args()

    load_env(Path(__file__).with_name(".env"))
    kinds = ["phish", "trusted"] if args.which == "both" else [args.which]
    sender = os.environ.get("DEMO_FROM", "bot-inbox@example.com") if args.dry_run else need("DEMO_FROM")
    to = os.environ.get("DEMO_TO") or sender

    for kind in kinds:
        msg = build(kind, sender, to)
        if args.dry_run:
            print(msg.as_string(), "\n" + "=" * 60)
            continue
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender, need("DEMO_APP_PASSWORD").replace(" ", ""))
            smtp.send_message(msg)
        print(f"Sent {kind} email from {sender} to {to}: {msg['Subject']}")


if __name__ == "__main__":
    main()
