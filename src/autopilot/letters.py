"""Draft the message the patient sends through the provider portal for a finding."""

from __future__ import annotations

from autopilot.reconcile import Finding


def draft(finding: Finding, patient: str) -> str | None:
    """Return a portal message for findings that need one, else None.

    Args:
        finding: A reconciliation finding.
        patient: Name to sign the message with.
    """
    b, e = finding.bill, finding.eob
    ref = f"Statement {b.statement_id}, date of service {b.service_date:%m/%d/%Y}"
    match finding.kind:
        case "overbilled" if e is not None:
            body = (
                f"My insurer's Explanation of Benefits for claim {e.claim_id} (processed "
                f"{e.processed_date:%m/%d/%Y}) shows my patient responsibility is "
                f"${e.patient_responsibility}. Your statement bills ${b.amount_due}, which is "
                f"${finding.overcharge} more. Please correct the balance to "
                f"${e.patient_responsibility} and send an updated statement. I will pay the "
                "corrected amount once it is reflected. The EOB is attached."
            )
        case "denied" if e is not None:
            body = (
                f"My insurer denied claim {e.claim_id} ({e.denial_reason or 'no reason given'}). "
                "I am filing an appeal. Please place this balance on hold until the appeal is "
                "decided, and send any prior-authorization or medical-necessity records that "
                "support it."
            )
        case "no_claim":
            body = (
                "My insurer has no claim on file for this service. Please submit the claim to "
                "my insurance and hold this balance until it is processed."
            )
        case _:
            return None
    return f"Re: {ref}\n\n{body}\n\nThank you,\n{patient}"


def appeal(finding: Finding, patient: str) -> str | None:
    """Return an insurer appeal for a denied claim, citing provider-side evidence if found.

    Args:
        finding: A reconciliation finding.
        patient: Name to sign the appeal with.
    """
    e, a = finding.eob, finding.authorization
    if finding.kind != "denied" or e is None:
        return None
    evidence = (
        f"{finding.bill.provider}'s records show prior authorization {a.auth_id} for {a.service}, "
        f"status {a.status}, valid {a.valid_from:%m/%d/%Y} through {a.valid_to:%m/%d/%Y}, which "
        f"covers the {e.service_date:%m/%d/%Y} date of service. A copy is attached. Please "
        "reprocess the claim against that authorization."
        if a else
        "Please provide the specific clinical criteria used and reconsider the claim; I am "
        "requesting the supporting records from my provider."
    )
    return (
        f"Re: Appeal of claim {e.claim_id}, date of service {e.service_date:%m/%d/%Y}\n\n"
        f"I am appealing the denial of claim {e.claim_id} (processed {e.processed_date:%m/%d/%Y}, "
        f"reason: \"{e.denial_reason or 'none given'}\"). {evidence}\n\nThank you,\n{patient}"
    )
