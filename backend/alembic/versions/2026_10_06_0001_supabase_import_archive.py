"""Private, lossless provenance for the Supabase demo import."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "supabase_import_0001"
down_revision = "mobile_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA migration_archive")
    op.execute("REVOKE ALL ON SCHEMA migration_archive FROM PUBLIC")
    op.create_table(
        "supabase_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_project", sa.String(64), nullable=False, unique=True),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("counts", postgresql.JSONB(), nullable=False),
        schema="migration_archive",
    )
    op.create_table(
        "supabase_records",
        sa.Column("source_project", sa.String(64), primary_key=True),
        sa.Column("source_table", sa.String(64), primary_key=True),
        sa.Column("source_id", sa.Text(), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("migration_archive.supabase_batches.id"), nullable=False),
        sa.Column("target_table", sa.String(64), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        schema="migration_archive",
    )
    op.create_index("ix_supabase_records_batch", "supabase_records", ["batch_id"], schema="migration_archive")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA migration_archive FROM PUBLIC")


def downgrade() -> None:
    # Refuse to erase the only migrated copy of archived history.
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM migration_archive.supabase_records) "
               "THEN RAISE EXCEPTION 'Export the migration archive before downgrade'; END IF; END $$")
    op.drop_table("supabase_records", schema="migration_archive")
    op.drop_table("supabase_batches", schema="migration_archive")
    op.execute("DROP SCHEMA migration_archive")
