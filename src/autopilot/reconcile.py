"""Cross-portal reconciliation of provider bills against insurer EOBs.

Pure core: parsed records in, findings out. No I/O, no clock; ``today`` is passed in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

# Most ACA plans allow 180 days from the denial notice to file an internal appeal.
APPEAL_WINDOW = timedelta(days=180)

# Portals disagree on date formats; the Bot copies whatever the page shows.
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y")

Kind = Literal["overbilled", "denied", "no_claim", "ok"]


@dataclass(frozen=True)
class Eob:
    """One insurer Explanation of Benefits line, as shown on the insurer portal."""

    claim_id: str
    provider: str
    service_date: date
    description: str
    billed: Decimal
    patient_responsibility: Decimal
    status: Literal["paid", "denied"]
    processed_date: date
    denial_reason: str = ""


@dataclass(frozen=True)
class Bill:
    """One provider statement line, as shown on the provider portal."""

    statement_id: str
    claim_id: str | None
    provider: str
    service_date: date
    description: str
    amount_due: Decimal
    due_date: date


@dataclass(frozen=True)
class Finding:
    """What the patient should do about one bill, with the evidence behind it."""

    kind: Kind
    bill: Bill
    eob: Eob | None
    should_owe: Decimal | None
    deadline: date
    action: str
    summary: str

    @property
    def overcharge(self) -> Decimal:
        """Amount billed above what the EOB says the patient owes (0 if none)."""
        if self.should_owe is None:
            return Decimal(0)
        return max(self.bill.amount_due - self.should_owe, Decimal(0))


def parse_money(value: Any) -> Decimal:
    """Parse ``1234.5``, ``"$1,234.50"`` or ``"(12.00)"`` into a Decimal.

    Raises:
        ValueError: If the value has no digits.
    """
    text = str(value).strip()
    negative = text.startswith("(") and text.endswith(")") or text.startswith("-")
    digits = re.sub(r"[^0-9.]", "", text)
    if not digits:
        raise ValueError(f"not a money amount: {value!r}")
    amount = Decimal(digits).quantize(Decimal("0.01"))
    return -amount if negative else amount


def parse_date(value: str) -> date:
    """Parse any date format the portals use.

    Raises:
        ValueError: If no known format matches.
    """
    text = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognized date: {value!r}")


def _claim_id(value: Any) -> str | None:
    # Portals pad or decorate claim numbers ("Claim #CLM-1001"); compare the bare id.
    if value in (None, "", "N/A", "None"):
        return None
    return re.sub(r"^(claim\s*)?#?\s*", "", str(value).strip(), flags=re.I).upper()


def parse_eob(raw: dict[str, Any]) -> Eob:
    """Build an Eob from the Bot's loosely typed extraction."""
    return Eob(
        claim_id=_claim_id(raw["claim_id"]) or "",
        provider=raw["provider"],
        service_date=parse_date(raw["service_date"]),
        description=raw.get("description", ""),
        billed=parse_money(raw["billed"]),
        patient_responsibility=parse_money(raw["patient_responsibility"]),
        status="denied" if str(raw["status"]).strip().lower().startswith("den") else "paid",
        processed_date=parse_date(raw["processed_date"]),
        denial_reason=raw.get("denial_reason", ""),
    )


def parse_bill(raw: dict[str, Any]) -> Bill:
    """Build a Bill from the Bot's loosely typed extraction."""
    return Bill(
        statement_id=str(raw["statement_id"]),
        claim_id=_claim_id(raw.get("claim_id")),
        provider=raw["provider"],
        service_date=parse_date(raw["service_date"]),
        description=raw.get("description", ""),
        amount_due=parse_money(raw["amount_due"]),
        due_date=parse_date(raw["due_date"]),
    )


def classify(bill: Bill, eob: Eob | None) -> Finding:
    """Decide what to do about one bill given its matching EOB, if any.

    Args:
        bill: The provider statement line.
        eob: The insurer EOB with the same claim id, or None if the insurer has no record.

    Returns:
        A Finding; ``deadline`` is the date by which the patient must act.
    """
    if eob is None:
        return Finding(
            "no_claim", bill, None, None, bill.due_date,
            "hold payment; ask provider to submit the claim to insurance",
            f"{bill.provider} billed ${bill.amount_due} for {bill.description} "
            "but the insurer has no claim for it.",
        )
    if eob.status == "denied":
        return Finding(
            "denied", bill, eob, eob.patient_responsibility, eob.processed_date + APPEAL_WINDOW,
            "hold payment; file an insurance appeal",
            f"Insurer denied {eob.claim_id} ({eob.denial_reason or 'no reason given'}); "
            f"${bill.amount_due} is on hold until the appeal is decided.",
        )
    if bill.amount_due > eob.patient_responsibility:
        overage = bill.amount_due - eob.patient_responsibility
        return Finding(
            "overbilled", bill, eob, eob.patient_responsibility, bill.due_date,
            f"dispute; pay only ${eob.patient_responsibility}",
            f"{bill.provider} billed ${bill.amount_due} for {eob.claim_id}, but the EOB says "
            f"you owe ${eob.patient_responsibility}: overbilled by ${overage}.",
        )
    return Finding(
        "ok", bill, eob, eob.patient_responsibility, bill.due_date,
        f"pay ${bill.amount_due}",
        f"{bill.provider} bill for {eob.claim_id} matches the EOB.",
    )


def reconcile(bills: list[Bill], eobs: list[Eob]) -> list[Finding]:
    """Match every bill to its EOB by claim id and classify it.

    Returns:
        Findings ordered by deadline, with money-at-stake kinds first on ties.
    """
    by_claim = {e.claim_id: e for e in eobs}
    findings = [classify(b, by_claim.get(b.claim_id) if b.claim_id else None) for b in bills]
    urgency = {"overbilled": 0, "denied": 1, "no_claim": 2, "ok": 3}
    return sorted(findings, key=lambda f: (f.deadline, urgency[f.kind]))
