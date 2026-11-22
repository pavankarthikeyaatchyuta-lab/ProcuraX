from datetime import datetime, timedelta
from decimal import Decimal
from .db import now
from .domain import rows, dec
from .models import Audit, Basket, Document


def quality_metrics(db, business):
    events = rows(db, Audit, business.id)
    feedback = {}
    for event in sorted(events, key=lambda e: e.at):
        if event.action == "alert.feedback":
            feedback[(event.target, event.detail.get("type"))] = event.detail.get(
                "useful"
            )
    docs = [d for d in rows(db, Document, business.id) if d.status == "verified"]
    corrections = 0
    elapsed = []
    agreements = {"structured": {}, "ocr": {}}
    for d in docs:
        final = next(
            (v["verified"] for v in reversed(d.versions) if "verified" in v), None
        )
        if not final:
            continue
        source = "structured" if d.mime == "application/json" else "ocr"
        changed = False
        for key in ("invoice_no", "date", "total"):
            original = d.extracted.get(key, "")
            reviewed = final[key]
            if key == "total":
                try:
                    equal = abs(dec(original) - dec(reviewed)) <= Decimal(".02")
                except Exception:
                    equal = False
            else:
                equal = (
                    str(original).strip().casefold() == str(reviewed).strip().casefold()
                )
            measure = agreements[source].setdefault(key, {"correct": 0, "reviewed": 0})
            measure["reviewed"] += 1
            measure["correct"] += int(equal)
            changed |= not equal
        corrections += changed
        timestamp = next(
            (v.get("at") for v in reversed(d.versions) if "verified" in v), None
        )
        if timestamp:
            elapsed.append(
                max(0, (datetime.fromisoformat(timestamp) - d.created).total_seconds())
            )
    baskets = rows(db, Basket, business.id)
    accepted = [
        b
        for b in baskets
        if b.status in ("approved", "exporting", "partial", "exported")
    ]
    compliant = sum(
        sum((dec(l["cash_spend"]) for l in b.lines), Decimal(0)) <= b.budget
        for b in accepted
    )
    purchasers = {
        e.actor
        for e in events
        if e.at >= now() - timedelta(days=7) and e.action.startswith("basket.")
    }
    return {
        "alert_usefulness": sum(v is True for v in feedback.values()) / len(feedback)
        if feedback
        else None,
        "alert_feedback_count": len(feedback),
        "alert_usefulness_reason": None
        if feedback
        else "No owner/reviewer alert feedback yet",
        "review_corrections": corrections,
        "reviewed_header_agreement": agreements,
        "mean_invoice_processing_seconds": sum(elapsed) / len(elapsed)
        if elapsed
        else None,
        "budget_adherence": compliant / len(accepted) if accepted else None,
        "weekly_active_purchasers": len(purchasers),
        "extraction_launch_gate": "Not evaluated: independent, supplier-diverse labeled pilot corpus required for the 95% target",
        "matching_accuracy": None,
        "matching_accuracy_reason": "Reviewed suggestions are not an independent labeled matching benchmark",
    }
