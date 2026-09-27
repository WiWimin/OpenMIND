"""enable pgvector extension

Revision ID: 0002_enable_pgvector
Revises: 0001_baseline
Create Date: 2026-09-27

The pgvector/pgvector image only ships the extension binaries. The extension
must be enabled inside the target database before the ``vector`` type is usable.
This migration is intentionally idempotent so re-running it is harmless.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002_enable_pgvector"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # Drops the extension only. Dependent columns/tables are NOT cascaded, so a
    # downgrade fails loudly instead of silently destroying objects that rely on
    # the vector type. Drop those objects first if a downgrade is really needed.
    op.execute("DROP EXTENSION IF EXISTS vector")
