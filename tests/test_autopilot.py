"""Behavior tests: the demo data must produce the demo story, and the gate must hold."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from autopilot import cli, gate, reconcile

EXAMPLES = Path(__file__).parent.parent / "examples"


def _example(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def test_demo_records_tell_the_demo_story():
    report = cli.run_reconcile(_example("records.json"))
    by_stmt = {f["statement_id"]: f for f in report["findings"]}

    assert by_stmt["ST-88412"]["kind"] == "overbilled"
    assert by_stmt["ST-88412"]["overcharge"] == "372.00"
    assert "$40.00" in by_stmt["ST-88412"]["letter"]
    assert by_stmt["ST-88413"]["kind"] == "ok"
    assert by_stmt["ST-88413"]["letter"] is None
    assert by_stmt["ST-89107"]["kind"] == "denied"
    assert by_stmt["ST-89107"]["deadline"] == "2027-04-10"  # Oct 12 + 180 days
    assert by_stmt["ST-89530"]["kind"] == "no_claim"
    assert "$372.00 you don't owe" in report["summary"]
    assert report["findings"][0]["statement_id"] == "ST-88412"  # most urgent money first


def test_cross_portal_evidence_and_alerts():
    report = cli.run_reconcile(_example("records.json"))
    by_stmt = {f["statement_id"]: f for f in report["findings"]}

    # Hospital-side prior auth contradicts the insurer's "not on file" denial.
    mri = by_stmt["ST-89107"]
    assert mri["authorization"] == "PA-55120"
    assert "PA-55120" in mri["appeal"] and "10/02/2026" in mri["appeal"]
    # Bank autopay pays $412 against a bill where only $40 is owed; deadline moves to edit cutoff.
    er = by_stmt["ST-88412"]
    assert er["autopay_warning"].startswith("Scheduled $412.00")
    assert er["deadline"] == "2026-11-13"
    assert "Autopay of $412.00" in report["summary"]
    # Only the planted payee-change message is flagged; routine bank mail is not.
    assert [a["subject"] for a in report["alerts"]] == ["Payee update notice"]
    assert {"addresses AI assistants with instructions", "asks to change where money is sent",
            "asks to approve payments without confirmation"} <= set(report["alerts"][0]["reasons"])


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("$1,850.00", Decimal("1850.00")), (40, Decimal("40.00")), ("(12.50)", Decimal("-12.50"))],
)
def test_parse_money(raw, expected):
    assert reconcile.parse_money(raw) == expected


@pytest.mark.parametrize("raw", ["09/14/2026", "Sep 14, 2026", "2026-09-14", "September 14, 2026"])
def test_parse_date_accepts_every_portal_format(raw):
    assert reconcile.parse_date(raw) == date(2026, 9, 14)


def test_bill_under_eob_amount_is_ok():
    bill = reconcile.parse_bill(
        {"statement_id": "S", "claim_id": "C1", "provider": "P", "service_date": "2026-01-01",
         "amount_due": "10", "due_date": "2026-02-01"}
    )
    eob = reconcile.parse_eob(
        {"claim_id": "C1", "provider": "P", "service_date": "2026-01-01", "billed": "100",
         "patient_responsibility": "20", "status": "Paid", "processed_date": "2026-01-10"}
    )
    assert reconcile.classify(bill, eob).kind == "ok"


PORTALS = cli._portals(None)


def test_registered_sender_with_portal_link_is_trusted():
    out = cli.run_gate(_example("email_trusted.json"), PORTALS)
    assert out["verdict"] == "trusted"
    assert out["portal"]["id"] == "bluebonnet"


def test_impersonation_is_quarantined_with_every_reason():
    out = cli.run_gate(_example("email_phish.json"), PORTALS)
    reasons = " | ".join(out["reasons"])
    assert out["verdict"] == "quarantine" and out["portal"] is None
    assert "claims to be Cedar Hollow Credit Union" in reasons
    assert "imitates cedarhollowcu.example" in reasons
    assert "link text shows cedarhollowcu.example" in reasons
    assert "DMARC did not pass" in reasons


def test_registered_sender_claiming_another_portal_is_quarantined():
    email = {
        **_example("email_trusted.json"),
        "subject": "Cedar Hollow CU: new secure message",
        "links": [{"text": "Log in", "href": "https://cedarhollow-cu-secure.example/login"}],
    }
    reasons = " | ".join(gate.inspect_email(email, PORTALS).reasons)
    assert "registered for Bluebonnet Regional Medical Center" in reasons
    assert "claims to be Cedar Hollow Credit Union" in reasons


@pytest.mark.parametrize(
    ("href", "reason"),
    [
        ("https://bit.ly/abc", "shortener"),
        ("https://xn--bluebnnet-health-xyz.example/", "punycode"),
        ("https://evil.example/login", "outside Bluebonnet"),
        ("https://b1uebonnet-health.example/", "imitates bluebonnet-health.example"),
    ],
)
def test_bad_link_from_real_sender_is_quarantined(href, reason):
    email = {**_example("email_trusted.json"), "links": [{"text": "Log in", "href": href}]}
    verdict = gate.inspect_email(email, PORTALS)
    assert not verdict.trusted
    assert any(reason in r for r in verdict.reasons)
