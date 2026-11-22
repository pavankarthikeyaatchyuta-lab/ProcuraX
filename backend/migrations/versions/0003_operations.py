"""Branch-safe procurement operations; historical balances are unchanged."""

from alembic import op
import sqlalchemy as sa
from uuid import uuid4
from datetime import timedelta
from app.db import Base
from app import models

revision = "0003"
down_revision = "0002"
SCOPED = [
    "documents",
    "transactions",
    "lines",
    "movements",
    "stock_snapshots",
    "lost_sales",
    "receipts",
    "baskets",
    "order_attempts",
    "jobs",
    "audit_events",
]


def upgrade():
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            table.create(bind, checkfirst=True)
    for name in SCOPED:
        if "branch_id" not in {c["name"] for c in sa.inspect(bind).get_columns(name)}:
            op.add_column(name, sa.Column("branch_id", sa.String(), nullable=True))
            op.create_index(f"ix_{name}_branch_id", name, ["branch_id"])
    for business in bind.execute(sa.text("SELECT id FROM businesses")).mappings():
        bid = business["id"]
        branch = uuid4().hex
        bind.execute(
            sa.text(
                "INSERT INTO branches (id,business_id,code,name,address,budget,committed,manager_limit,version) VALUES (:id,:bid,'MAIN','Main Store','',200000,0,20000,1)"
            ),
            {"id": branch, "bid": bid},
        )
        for name in SCOPED:
            bind.execute(
                sa.text(
                    f"UPDATE {name} SET branch_id=:branch WHERE business_id=:bid AND branch_id IS NULL"
                ),
                {"branch": branch, "bid": bid},
            )
        for m in bind.execute(
            sa.text("SELECT user_id,role FROM memberships WHERE business_id=:bid"),
            {"bid": bid},
        ).mappings():
            bind.execute(
                sa.text(
                    "INSERT INTO branch_grants (id,business_id,branch_id,user_id,role) VALUES (:id,:bid,:branch,:user,:role)"
                ),
                {
                    "id": uuid4().hex,
                    "bid": bid,
                    "branch": branch,
                    "user": m["user_id"],
                    "role": m["role"],
                },
            )
        for p in bind.execute(
            sa.text(
                "SELECT id,manual_demand,storage_limit FROM products WHERE business_id=:bid"
            ),
            {"bid": bid},
        ).mappings():
            bind.execute(
                models.BranchProduct.__table__.insert().values(
                    id=uuid4().hex,
                    business_id=bid,
                    branch_id=branch,
                    product_id=p["id"],
                    manual_demand=p["manual_demand"],
                    storage_limit=p["storage_limit"],
                )
            )
        for t in bind.execute(
            sa.select(models.Transaction.__table__).where(
                models.Transaction.business_id == bid,
                models.Transaction.kind == "purchase",
                models.Transaction.active == True,
            )
        ).mappings():
            if t["supplier_id"]:
                bind.execute(
                    models.Payable.__table__.insert().values(
                        id=uuid4().hex,
                        business_id=bid,
                        branch_id=branch,
                        transaction_id=t["id"],
                        supplier_id=t["supplier_id"],
                        due=t["date"] + timedelta(days=14),
                        version=1,
                    )
                )


def downgrade():
    raise RuntimeError(
        "Restore the pre-upgrade backup rather than discarding operational records"
    )
