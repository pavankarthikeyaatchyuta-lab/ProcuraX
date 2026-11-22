"""Bind MFA proof to each session, including pre-enrollment sessions."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"


def upgrade():
    # A fresh 0001 uses current metadata; existing installations need the column.
    if "mfa_verified" not in {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns("sessions")
    }:
        op.add_column(
            "sessions",
            sa.Column(
                "mfa_verified", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
        )


def downgrade():
    op.drop_column("sessions", "mfa_verified")
