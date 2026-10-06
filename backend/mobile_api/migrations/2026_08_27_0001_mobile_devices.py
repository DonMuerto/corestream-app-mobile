"""
Migración Alembic del módulo móvil (§9.1 y §7.2).

Crea:
    - user_devices               (tokens FCM por usuario)
    - notification_preferences   (preferencias push, 1:1 con users)

Modifica (aditivo, retrocompatible):
    - notifications.incident_id  (UUID nullable, FK incidents.id)
    - notification_type_enum     (+ INCIDENT_REPORTED, INCIDENT_ASSIGNED)

INSTALACIÓN: copiar este archivo a backend/alembic/versions/ y ajustar
`down_revision` a la revisión head actual del proyecto (alembic heads).
Si el proyecto crea tablas con Base.metadata.create_all (main.py), las dos
tablas nuevas también se crean solas al importar mobile_api.models; esta
migración sigue siendo necesaria para incident_id y el enum.

Revision ID: mobile_0001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "mobile_0001"
down_revision = None  # <-- AJUSTAR a la head actual del proyecto
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------- user_devices
    op.create_table(
        "user_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fcm_token", sa.String(4096), nullable=False, unique=True),
        sa.Column("platform", sa.String(10), nullable=False),
        sa.Column("device_name", sa.String(120), nullable=True),
        sa.Column("app_version", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_user_devices_user_id", "user_devices", ["user_id"])
    op.create_index("ix_user_devices_is_active", "user_devices", ["is_active"])

    # ------------------------------------------------ notification_preferences
    op.create_table(
        "notification_preferences",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ticket_assigned", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("question_asked", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ticket_completed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("incident_reported", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deadline_approaching", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("quiet_hours_start", sa.String(5), nullable=True),
        sa.Column("quiet_hours_end", sa.String(5), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # -------------------------------------------- notifications.incident_id (§7.2)
    op.add_column(
        "notifications",
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_notifications_incident_id",
        "notifications",
        "incidents",
        ["incident_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_notifications_incident_id", "notifications", ["incident_id"])

    # ------------------------------------- nuevos valores del enum (§7.2)
    # ALTER TYPE ... ADD VALUE no puede ejecutarse dentro de un bloque de
    # transacción en PostgreSQL: se usa autocommit_block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE notification_type_enum ADD VALUE IF NOT EXISTS 'INCIDENT_REPORTED'")
        op.execute("ALTER TYPE notification_type_enum ADD VALUE IF NOT EXISTS 'INCIDENT_ASSIGNED'")


def downgrade() -> None:
    op.drop_index("ix_notifications_incident_id", table_name="notifications")
    op.drop_constraint("fk_notifications_incident_id", "notifications", type_="foreignkey")
    op.drop_column("notifications", "incident_id")
    op.drop_table("notification_preferences")
    op.drop_index("ix_user_devices_is_active", table_name="user_devices")
    op.drop_index("ix_user_devices_user_id", table_name="user_devices")
    op.drop_table("user_devices")
    # Nota: PostgreSQL no permite eliminar valores de un enum; los valores
    # INCIDENT_* quedan en el tipo (inocuo).
