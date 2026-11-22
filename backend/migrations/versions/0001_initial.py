"""Initial procurement schema."""

from alembic import op
from migrations.legacy_models import Base

revision = "0001"
down_revision = None


def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind)
    for table in (
        "products",
        "quotes",
        "documents",
        "transactions",
        "lines",
        "movements",
        "stock_snapshots",
        "receipts",
        "baskets",
        "audit_events",
        "jobs",
    ):
        op.create_index(f"ix_{table}_business_id", table, ["business_id"])


def downgrade():
    Base.metadata.drop_all(op.get_bind())
