"""Gatekeeper: decide whether a "log in to view" email is a real portal notification.

Pure core. Nothing here fetches or opens a link: the email is only a trigger, and a
trusted verdict names a registered portal whose *registered* URL the Clerk Bot opens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

SHORTENERS = frozenset({"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "rb.gy"})

# Characters phishers swap in to make a domain read like a real one.
_CONFUSABLES = str.maketrans({"0": "o", "1": "l", "3": "e", "5": "s", "@": "a"})


@dataclass(frozen=True)
class Portal:
    """A portal the user registered once: who may notify, and where its links may point."""

    id: str
    name: str
    login_url: str
    sender_domains: tuple[str, ...]
    link_domains: tuple[str, ...]
    senders: tuple[str, ...] = ()  # exact addresses, e.g. a demo sender on gmail.com
    aliases: tuple[str, ...] = ()  # names an impersonator would use in the display name


@dataclass(frozen=True)
class Verdict:
    """Gatekeeper result. ``portal`` is set only when the email is trusted."""

    trusted: bool
    portal: Portal | None
    reasons: tuple[str, ...]


# Content inside a trusted portal is still untrusted data. These patterns catch text that
# tries to steer an agent, or the classic "we changed our bank details" payment fraud.
_INJECTION_PATTERNS = (
    (r"\b(ai|assistants?|agents?|bots?|automated|llms?)\b[^.]{0,80}\b(should|must|are instructed|please)\b",
     "addresses AI assistants with instructions"),
    (r"ignore (all |any )?(previous|prior|earlier) (instructions|rules)",
     "tries to override the assistant's instructions"),
    (r"\b(new|updated|changed?)\b[^.]{0,30}\b(remittance|bank|routing|payee|payment) "
     r"(account|details|information|instructions)\b|\bupdate the payee\b",
     "asks to change where money is sent"),
    (r"\bapprove (all |any )?(pending|scheduled) payments?\b|without (further )?confirmation",
     "asks to approve payments without confirmation"),
)


def scan_message(text: str) -> tuple[str, ...]:
    """Return why a portal message looks like an injection or payee-change attempt.

    Args:
        text: Subject and body of one portal message.

    Returns:
        Reasons; empty if the message looks benign. Flagged messages are reported, never acted on.
    """
    lowered = text.lower()
    return tuple(reason for pattern, reason in _INJECTION_PATTERNS if re.search(pattern, lowered))


def load_portals(raw: list[dict[str, Any]]) -> list[Portal]:
    """Build the portal registry from its JSON form."""
    return [
        Portal(
            id=p["id"], name=p["name"], login_url=p["login_url"],
            sender_domains=tuple(d.lower() for d in p.get("sender_domains", [])),
            link_domains=tuple(d.lower() for d in p.get("link_domains", [])),
            senders=tuple(s.lower() for s in p.get("senders", [])),
            aliases=tuple(a.lower() for a in p.get("aliases", [p["name"]])),
        )
        for p in raw
    ]


def _host(url: str) -> str:
    host = (urlsplit(url if "//" in url else f"//{url}").hostname or "").lower()
    return host.removeprefix("www.")


def _within(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == d or host.endswith(f".{d}") for d in domains)


def _skeleton(host: str) -> str:
    # Collapse look-alike glyphs and separators so "mych4rt-secure.com" ~ "mychart.com".
    return re.sub(r"[^a-z]", "", host.translate(_CONFUSABLES).replace("rn", "m").removeprefix("www"))


def _lookalike(host: str, portals: list[Portal]) -> str | None:
    """Return the registered domain ``host`` imitates, if it imitates one without being it."""
    for p in portals:
        for d in p.link_domains + p.sender_domains:
            if _within(host, (d,)):
                return None
            base = _skeleton(d.rsplit(".", 1)[0])
            if base and len(base) >= 5 and base in _skeleton(host):
                return d
    return None


def _match_sender(address: str, portals: list[Portal]) -> Portal | None:
    domain = address.rsplit("@", 1)[-1]
    return next(
        (p for p in portals if address in p.senders or _within(domain, p.sender_domains)), None
    )


def inspect_email(email: dict[str, Any], portals: list[Portal]) -> Verdict:
    """Classify one notification email without opening anything it links to.

    Args:
        email: ``from_name``, ``from_address``, ``subject``, optional ``auth`` (the
            ``Authentication-Results`` header text) and ``links`` as ``[{text, href}]``.
        portals: The user's registered portals.

    Returns:
        A trusted Verdict naming the portal, or an untrusted one listing every reason.
    """
    address = email.get("from_address", "").strip().lower()
    claimed = f"{email.get('from_name', '')} {email.get('subject', '')}".lower()
    portal = _match_sender(address, portals)
    reasons: list[str] = []

    impersonated = [
        p.name for p in portals if p is not portal and any(a in claimed for a in p.aliases)
    ]
    if portal is None:
        reasons.append(
            f"sender {address or '(none)'} is not registered"
            + (f" but the email claims to be {', '.join(impersonated)}" if impersonated else "")
        )
    elif impersonated:
        # A real sender for one portal claiming to be another is a hijacked or spoofed account.
        reasons.append(
            f"sender is registered for {portal.name} but the email claims to be "
            + ", ".join(impersonated)
        )

    auth = email.get("auth", "").lower()
    for check in ("spf", "dkim", "dmarc"):
        if re.search(rf"{check}=(fail|softfail|none)", auth):
            reasons.append(f"{check.upper()} did not pass")

    for link in email.get("links", []):
        host = _host(link.get("href", ""))
        shown = _host(link.get("text", "")) if "." in link.get("text", "") else ""
        if host.startswith("xn--") or ".xn--" in host:
            reasons.append(f"link uses a punycode domain: {host}")
        if host in SHORTENERS:
            reasons.append(f"link hides its destination behind a shortener: {host}")
        if shown and shown != host:
            reasons.append(f"link text shows {shown} but points to {host}")
        if (imitated := _lookalike(host, portals)) is not None:
            reasons.append(f"link domain {host} imitates {imitated}")
        elif portal is not None and host and not _within(host, portal.link_domains):
            reasons.append(f"link points outside {portal.name}: {host}")

    unique = tuple(dict.fromkeys(reasons))
    return Verdict(not unique and portal is not None, portal if not unique else None, unique)
