"""
Esquemas de validación para Equipos (Team).

Un Team es un agrupador liviano de Épicas (posiblemente repartidas entre
varias Application) que representa el "mini-proyecto" de un equipo de
estudiantes dentro de la software factory. Ver docstring de
app/models/team.py para el contexto completo.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.epic import EpicResponse


class TeamCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=1000)

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("El nombre del equipo no puede estar vacío")
        return v.strip()


class TeamUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("El nombre del equipo no puede estar vacío")
        return v.strip() if v else v


class TeamMemberCreate(BaseModel):
    """
    Agrega un integrante a un equipo. Dos formas de uso:
    - Suelto: solo `name` (y opcionalmente `email` de referencia) — no
      requiere que la persona tenga cuenta en CoreStream.
    - Vinculado: `userId` de un User ya existente en el sistema — `name`/
      `email` se completan automáticamente desde ese usuario si no se
      envían explícitos.
    """
    name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    user_id: Optional[UUID] = Field(None, alias="userId")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("El nombre no puede estar vacío")
        return v.strip() if v else v


class TeamMemberEntry(BaseModel):
    id: UUID
    name: str
    email: Optional[str] = None
    user_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


class TeamResponse(BaseModel):
    """
    Respuesta de listado: un equipo con sus estadísticas agregadas, sin el
    detalle completo de tickets de cada épica (para que listar equipos sea
    liviano). Para el detalle completo ver TeamDetailResponse.
    """
    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime

    epic_count: int = 0
    total_tickets: int = 0
    completed_tickets: int = 0
    progress: float = 0.0
    member_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class TeamDetailResponse(TeamResponse):
    """Detalle de un equipo con sus épicas y sus integrantes (vista Equipos)."""
    epics: List[EpicResponse] = []
    members: List[TeamMemberEntry] = []
