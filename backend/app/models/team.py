from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseEntity

if TYPE_CHECKING:
    from app.models.epic import Epic


class Team(Base, BaseEntity):
    """
    Modelo de Base de Datos para Equipos (CoreStream).

    CONTEXTO: Alloxentric opera como software factory con convenio con
    universidades (DuocUC, UTEM). Cada semestre reparte decenas de proyectos
    (Application) entre muchos equipos de estudiantes, y cada equipo suele
    trabajar un conjunto propio de Épicas — a veces dentro de una misma
    Application, a veces repartidas entre varias. `Team` es un agrupador
    liviano (solo nombre + descripción) para poder ver y evaluar ese
    conjunto de Épicas como una unidad ("mini-proyecto" del equipo), sin
    modelar membresías individuales de estudiantes: los estudiantes no usan
    CoreStream, quien lo usa es el Team Leader interno de Alloxentric que
    hace seguimiento por fuera. Por eso esto es un catálogo de etiquetas,
    no un sistema de roles/permisos.
    """
    __tablename__ = "teams"

    # Nombre del equipo (p.ej. "Equipo A - DuocUC - 2026-1"). Único para
    # evitar duplicados accidentales al crear equipos "al vuelo".
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    # Contexto adicional libre (universidad, semestre, integrantes, etc.)
    # Se deja como texto libre en vez de columnas estructuradas (universidad,
    # semestre) porque hoy no hay necesidad de filtrar/reportar por esos
    # campos — si aparece, es fácil promoverlos a columnas reales después.
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Un equipo puede tener épicas en una o varias aplicaciones distintas.
    # No se usa cascade delete: borrar un equipo no debe borrar el trabajo
    # ya hecho, solo desasociarlo (ver Epic.team_id, ondelete="SET NULL").
    epics: Mapped[list["Epic"]] = relationship(
        lazy="raise_on_sql",
        back_populates="team",
    )
