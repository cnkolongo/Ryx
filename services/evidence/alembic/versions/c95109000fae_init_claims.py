"""init_claims

Revision ID: c95109000fae
Revises: 
Create Date: 2026-03-06 17:04:22.898909

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c95109000fae'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "claims",
        sa.Column("claim_id", sa.String(36), primary_key=True),
        sa.Column("encounter_id", sa.String(36), nullable=True),
        sa.Column("patient_id", sa.String(36), nullable=True),
        sa.Column("report_id", sa.String(36), nullable=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("criticality", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("evidence_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("validated_by", sa.String(64), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_claims_encounter_id", "claims", ["encounter_id"])
    op.create_index("ix_claims_patient_id", "claims", ["patient_id"])
    op.create_index("ix_claims_report_id", "claims", ["report_id"])
    op.create_index("ix_claims_status", "claims", ["status"])
    op.create_index("ix_claims_type", "claims", ["type"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("claims")
