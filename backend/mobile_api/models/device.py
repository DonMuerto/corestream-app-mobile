"""
Modelos de dispositivos móviles y preferencias de notificación push.

Corresponden a la sección 9.1 de la especificación:
    - user_devices: tokens FCM registrados por usuario.
    - notification_preferences: preferencias push 1:1 con users, creada
      perezosamente con valores por defecto la primera vez que se consulta.

Ambos modelos usan la misma Base declarativa del proyecto, de modo que
Base.metadata.create_all (startup) y Alembic los reconocen al importarlos.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID as PyUUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseEntity


class DevicePlatform(str, Enum):
    """Plataformas soportadas por la app móvil."""

    ANDROID = "ANDROID"
    IOS = "IOS"


class UserDevice(Base, BaseEntity):
    """
    Dispositivo móvil registrado para recibir notificaciones push (FCM).

    Atributos:
        user_id: Usuario propietario del dispositivo.
        fcm_token: Token de registro de Firebase Cloud Messaging (único).
        platform: ANDROID o IOS (se valida en el esquema Pydantic; se
            almacena como texto para mantener la migración portable).
        device_name: Nombre legible del dispositivo (opcional).
        app_version: Versión de la app instalada (opcional).
        is_active: False cuando FCM reporta el token como inválido o el
            usuario cierra sesión en el dispositivo.
        last_seen_at: Último registro o refresco del token.
    """

    __tablename__ = "user_devices"

    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Usuario propietario del dispositivo",
    )

    fcm_token: Mapped[str] = mapped_column(
        String(4096),
        nullable=False,
        unique=True,
        doc="Token de registro emitido por Firebase Cloud Messaging",
    )

    platform: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Plataforma del dispositivo: ANDROID | IOS",
    )

    device_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        doc="Nombre legible del dispositivo (ej. 'Pixel 8 de Diego')",
    )

    app_version: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Versión de la app móvil instalada",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        doc="Indica si el dispositivo puede recibir push",
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Último registro o refresco del token",
    )

    user = relationship("User", lazy="raise_on_sql", doc="Usuario propietario")


class NotificationPreference(Base):
    """
    Preferencias de notificación push del usuario (relación 1:1 con users).

    Si el usuario nunca configuró preferencias, no existe fila: el servicio
    devuelve los valores por defecto (todo activado, sin horario de silencio)
    y crea la fila en la primera escritura.
    """

    __tablename__ = "notification_preferences"

    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Usuario al que pertenecen las preferencias",
    )

    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, doc="Interruptor global de push")
    ticket_assigned: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, doc="Push al asignar/redirigir un ticket")
    question_asked: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, doc="Push cuando se plantea una pregunta")
    ticket_completed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, doc="Push cuando se completa un ticket")
    incident_reported: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, doc="Push cuando se reporta una incidencia")
    deadline_approaching: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, doc="Push de vencimiento próximo")

    quiet_hours_start: Mapped[str | None] = mapped_column(
        String(5), nullable=True, doc="Inicio del horario de silencio 'HH:MM' (hora local del servidor)"
    )
    quiet_hours_end: Mapped[str | None] = mapped_column(
        String(5), nullable=True, doc="Fin del horario de silencio 'HH:MM'"
    )

    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now(), nullable=False)
