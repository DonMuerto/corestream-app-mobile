"""Recoverable ticket archive; retains children and history."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "ticket_archive_0001"
down_revision = "supabase_import_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tickets", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("archived_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_ticket_archived_by", "tickets", "users", ["archived_by_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_tickets_archived_at", "tickets", ["archived_at"], postgresql_where=sa.text("archived_at IS NOT NULL"))


def downgrade():
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM tickets WHERE archived_at IS NOT NULL) "
               "THEN RAISE EXCEPTION 'Restore archived tickets before downgrade'; END IF; END $$")
    op.drop_index("ix_tickets_archived_at", table_name="tickets")
    op.drop_constraint("fk_ticket_archived_by", "tickets", type_="foreignkey")
    op.drop_column("tickets", "archived_by_id")
    op.drop_column("tickets", "archived_at")
