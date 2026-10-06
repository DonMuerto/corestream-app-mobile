"""
Esquemas Pydantic para dispositivos y preferencias de notificación (§4.1–4.5).
"""

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

from mobile_api.models.device import DevicePlatform

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class DeviceRegister(BaseModel):
    """Cuerpo de POST /devices/ — registro/refresco de un token FCM."""

    fcm_token: str
    platform: DevicePlatform
    device_name: Optional[str] = None
    app_version: Optional[str] = None

    @field_validator("fcm_token")
    @classmethod
    def validate_fcm_token(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El token FCM no puede estar vacío")
        if len(v) > 4096:
            raise ValueError("El token FCM supera la longitud máxima (4096)")
        return v

    @field_validator("device_name")
    @classmethod
    def validate_device_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 120:
            raise ValueError("El nombre del dispositivo supera los 120 caracteres")
        return v

    @field_validator("app_version")
    @classmethod
    def validate_app_version(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 20:
            raise ValueError("La versión de la app supera los 20 caracteres")
        return v


class DeviceResponse(BaseModel):
    """Respuesta de dispositivo registrado (§4.1, §4.2)."""

    id: UUID
    user_id: UUID
    platform: str
    device_name: Optional[str] = None
    app_version: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


class NotificationPreferencesResponse(BaseModel):
    """Respuesta de GET/PUT /devices/preferences (§4.4, §4.5)."""

    push_enabled: bool = True
    ticket_assigned: bool = True
    question_asked: bool = True
    ticket_completed: bool = True
    incident_reported: bool = True
    deadline_approaching: bool = True
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None

    model_config = {"from_attributes": True}


class NotificationPreferencesUpdate(BaseModel):
    """Cuerpo de PUT /devices/preferences — actualización parcial (§4.5)."""

    push_enabled: Optional[bool] = None
    ticket_assigned: Optional[bool] = None
    question_asked: Optional[bool] = None
    ticket_completed: Optional[bool] = None
    incident_reported: Optional[bool] = None
    deadline_approaching: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None

    @field_validator("quiet_hours_start", "quiet_hours_end")
    @classmethod
    def validate_hhmm(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _HHMM.match(v):
            raise ValueError("El horario de silencio debe tener formato HH:MM")
        return v

    @model_validator(mode="after")
    def validate_quiet_hours_pair(self):
        """Ambos extremos del horario de silencio se envían juntos (o ninguno)."""
        provided = self.model_fields_set
        if ("quiet_hours_start" in provided) != ("quiet_hours_end" in provided):
            raise ValueError("quiet_hours_start y quiet_hours_end deben enviarse juntos")
        return self
