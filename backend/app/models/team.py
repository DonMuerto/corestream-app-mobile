from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseEntity

if TYPE_CHECKING:
    from app.models.epic import Epic
    from app.models.team_member import TeamMember


class Team(Base, BaseEntity):
    """
    Modelo de Base de Datos para Equipos (CoreStream).

    CONTEXTO: Alloxentric opera como software factory con convenio con
    universidades (DuocUC, UTEM). Cada semestre reparte decenas de proyectos
    (Application) entre muchos equipos de estudiantes, y cada equipo suele
    trabajar un conjunto propio de Épicas — a veces dentro de una misma
    Application, a veces repartidas entre varias. `Team` es un agrupador
    liviano para poder ver y evaluar ese conjunto de Épicas como una unidad
    ("mini-proyecto" del equipo) y, opcionalmente, quién lo integra.

    Los integrantes (`TeamMember`) NO son un sistema de roles/permisos: la
    gran mayoría de los estudiantes nunca tiene cuenta en CoreStream (quien
    usa la herramienta es el Team Leader interno de Alloxentric). Por eso un
    integrante puede ser solo un nombre suelto (para un control general,
    "quién trabajó en esto") o, si el Team Leader lo necesita, puede
    vincularse a un User real ya existente en el sistema (para asignarle
    tickets con precisión). Ambos casos conviven — se adapta al nivel de
    control que Karina quiera en cada caso, no al revés.
    """
    __tablename__ = "teams"

    # Nombre del equipo (p.ej. "Equipo A - DuocUC - 2026-1"). Único para
    # evitar duplicados accidentales al crear equipos "al vuelo".
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    # Contexto adicional libre (universidad, semestre, etc.)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Un equipo puede tener épicas en una o varias aplicaciones distintas.
    # No se usa cascade delete: borrar un equipo no debe borrar el trabajo
    # ya hecho, solo desasociarlo (ver Epic.team_id, ondelete="SET NULL").
    epics: Mapped[list["Epic"]] = relationship(
        lazy="raise_on_sql",
        back_populates="team",
    )

    # Integrantes del equipo — ver TeamMember para el porqué de que sean
    # opcionalmente "sueltos" (solo nombre) u opcionalmente vinculados a un
    # User real. Estos sí se borran en cascada: son propios del equipo, no
    # trabajo entregado.
    members: Mapped[list["TeamMember"]] = relationship(
        lazy="raise_on_sql",
        back_populates="team",
        cascade="all, delete-orphan",
        order_by="TeamMember.created_at",
    )
