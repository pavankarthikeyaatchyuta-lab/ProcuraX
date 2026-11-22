"""Hourly sync and daily document retention, run as one scheduler process."""

import time
from datetime import timedelta
from pathlib import Path
from sqlalchemy import select
from .db import SessionLocal, now
from .models import Business, Integration, Job, Document
from .integrations import enqueue
from .domain import audit


def tick():
    with SessionLocal() as db:
        for business in db.scalars(select(Business)).all():
            i = db.get(Integration, business.id)
            active = db.scalar(
                select(Job).where(
                    Job.business_id == business.id,
                    Job.kind == "zoho_sync",
                    Job.status.in_(["running", "queued"]),
                )
            )
            if (
                i
                and i.organization_id
                and not active
                and (not i.last_sync or now() - i.last_sync >= timedelta(hours=1))
            ):
                job = Job(business_id=business.id, kind="zoho_sync")
                db.add(job)
                db.commit()
                try:
                    enqueue(job.id)
                except Exception:
                    job.status = "failed"
                    job.error = "Queue unavailable"
                    db.commit()
            cutoff = now() - timedelta(
                days=business.settings.get("retention_days", 365)
            )
            for d in db.scalars(
                select(Document).where(
                    Document.business_id == business.id, Document.created < cutoff
                )
            ).all():
                if d.status == "queued":
                    continue
                path = Path(d.path)
                if path.is_file():
                    path.unlink()
                    audit(
                        db, business.id, "scheduler", "document.retention_deleted", d.id
                    )
            db.commit()


if __name__ == "__main__":
    while True:
        tick()
        time.sleep(60)
