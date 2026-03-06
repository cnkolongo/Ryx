"""init_patients_encounters_labs

Revision ID: b99b68c3f59e
Revises: 
Create Date: 2026-03-06 17:03:59.721374

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b99b68c3f59e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "patients",
        sa.Column("patient_id", sa.String(36), primary_key=True),
        sa.Column("demographics", sa.JSON(), nullable=True),
        sa.Column("identifiers", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("external_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("quality_flags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "encounters",
        sa.Column("encounter_id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False),
        sa.Column("encounter_type", sa.String(32), nullable=False, server_default="outpatient"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("service", sa.String(128), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_encounters_patient_id", "encounters", ["patient_id"])

    op.create_table(
        "lab_results",
        sa.Column("lab_id", sa.String(36), primary_key=True),
        sa.Column("encounter_id", sa.String(36), sa.ForeignKey("encounters.encounter_id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=True),
        sa.Column("test", sa.String(128), nullable=False),
        sa.Column("value_numeric", sa.Numeric(12, 4), nullable=True),
        sa.Column("value_text", sa.String(256), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("ref_range", sa.JSON(), nullable=True),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("extracted_by", sa.String(32), nullable=False, server_default="ocr"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lab_results_encounter_id", "lab_results", ["encounter_id"])
    op.create_index("ix_lab_results_patient_id", "lab_results", ["patient_id"])
    op.create_index("ix_lab_results_test", "lab_results", ["test"])
    op.create_index("ix_lab_results_date", "lab_results", ["date"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("lab_results")
    op.drop_table("encounters")
    op.drop_table("patients")
