"""purpose model overrides

Revision ID: 0015_purpose_models
Revises: 0014_minutes_template
Create Date: 2026-10-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_purpose_models"
down_revision: str | None = "0014_minutes_template"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_model_configs",
        sa.Column(
            "llm_purpose_models",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_model_configs", "llm_purpose_models")
