from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID as PyUUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseEntity

if TYPE_CHECKING:
    from app.models.team import Team
    from app.models.user import User


class TeamMember(Base, BaseEntity):
    """
    Integrante de un Equipo (ver docstring de Team para el contexto).

    Puede ser:
    - Un nombre suelto (user_id=None): un estudiante que no tiene cuenta en
      CoreStream. Basta con anotar quién es, sin dar de alta nada.
    - Un integrante vinculado (user_id set): referencia a un User ya
      existente en el sistema (típicamente un DEVELOPER). Permite ver, por
      ejemplo, cuántos tickets tiene asignados sin duplicar esa información.

    Dar de alta una cuenta nueva en CoreStream sigue siendo exclusivo de
    ADMIN vía invitación (ver routers/invitations.py) — este modelo no lo
    reemplaza ni lo evita, solo referencia cuentas que ya existen.
    """
    __tablename__ = "team_members"

    team_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team: Mapped["Team"] = relationship(lazy="raise_on_sql", back_populates="members")

    # Si más adelante un ADMIN invita a esta persona como User real, el
    # Team Leader puede editar esta fila para vincularla — no hay pérdida
    # de datos si el User se borra después, solo se desvincula.
    user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user: Mapped["User | None"] = relationship(lazy="raise_on_sql")

    # Nombre a mostrar. Si está vinculado a un User, se copia su fullName al
    # crear el integrante (snapshot, no vive) — así el nombre no cambia bajo
    # los pies si el usuario edita su perfil después, pero tampoco hace
    # falta re-consultar el User solo para listar integrantes.
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Contacto de referencia opcional — útil incluso sin cuenta en el sistema.
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
