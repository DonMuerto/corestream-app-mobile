"""Esquemas de la extensión de autenticación (§4.6 y §7.3)."""

from typing import Optional

from pydantic import BaseModel, field_validator

from mobile_api.models.device import DevicePlatform


class LogoutRequest(BaseModel):
    """Cuerpo de POST /auth/logout (§4.6)."""

    refresh_token: str
    fcm_token: Optional[str] = None

    @field_validator("refresh_token")
    @classmethod
    def validate_refresh_token(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("El refresh token no puede estar vacío")
        return v.strip()


class LoginDevice(BaseModel):
    """
    Objeto opcional `device` para POST /auth/login (§7.3).

    Este esquema se exporta para que el equipo lo importe al aplicar el
    parche descrito en patches/CAMBIOS_EN_CODIGO_EXISTENTE.md.
    """

    fcm_token: str
    platform: DevicePlatform
    device_name: Optional[str] = None
    app_version: Optional[str] = None
