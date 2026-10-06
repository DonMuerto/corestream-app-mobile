"""
Router de dispositivos móviles y preferencias push (§4.1–4.5).

Prefijo: /devices
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import User
from mobile_api.models.device import NotificationPreference, UserDevice
from mobile_api.schemas.device import (
    DeviceRegister,
    DeviceResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)

router = APIRouter(prefix="/devices", tags=["Dispositivos móviles"])


# --------------------------------------------------------------- preferencias
# (declaradas antes que las rutas con parámetro para evitar colisiones)

async def _get_or_default_prefs(db: AsyncSession, user_id: str) -> NotificationPreference | None:
    return await db.get(NotificationPreference, user_id)


@router.get(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Obtener preferencias de notificación push",
)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """
    Devuelve las preferencias push del usuario autenticado (§4.4).

    Si el usuario nunca las configuró, devuelve los valores por defecto
    sin crear la fila (se crea perezosamente en la primera escritura).
    """
    prefs = await _get_or_default_prefs(db, current_user.id)
    if prefs is None:
        return NotificationPreferencesResponse()
    return NotificationPreferencesResponse.model_validate(prefs)


@router.put(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Actualizar preferencias de notificación push",
)
async def update_notification_preferences(
    payload: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """
    Actualización parcial de preferencias (§4.5): solo cambia lo enviado.
    Enviar quiet_hours_start = null y quiet_hours_end = null desactiva el
    horario de silencio.
    """
    prefs = await _get_or_default_prefs(db, current_user.id)
    if prefs is None:
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)

    for field in payload.model_fields_set:
        setattr(prefs, field, getattr(payload, field))

    await db.commit()
    await db.refresh(prefs)
    return NotificationPreferencesResponse.model_validate(prefs)


# --------------------------------------------------------------- dispositivos

@router.post(
    "/",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar dispositivo (token FCM)",
    description="Registra o refresca el token FCM del dispositivo del usuario autenticado",
)
async def register_device(
    payload: DeviceRegister,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeviceResponse:
    """
    Registra el dispositivo para notificaciones push (§4.1).

    Idempotente por fcm_token:
        - token nuevo                     -> 201 (alta)
        - token ya del mismo usuario      -> 200 (refresco de metadatos)
        - token de otro usuario           -> 200 (el teléfono cambió de sesión:
          se reasigna al usuario actual)
    """
    result = await db.execute(select(UserDevice).where(UserDevice.fcm_token == payload.fcm_token))
    device = result.scalar_one_or_none()

    if device is not None:
        device.user_id = current_user.id
        device.platform = payload.platform.value
        device.device_name = payload.device_name or device.device_name
        device.app_version = payload.app_version or device.app_version
        device.is_active = True
        response.status_code = status.HTTP_200_OK
    else:
        device = UserDevice(
            user_id=current_user.id,
            fcm_token=payload.fcm_token,
            platform=payload.platform.value,
            device_name=payload.device_name,
            app_version=payload.app_version,
        )
        db.add(device)

    await db.commit()
    await db.refresh(device)
    return DeviceResponse.model_validate(device)


@router.get(
    "/",
    response_model=list[DeviceResponse],
    summary="Listar dispositivos del usuario",
)
async def list_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DeviceResponse]:
    """Dispositivos registrados por el usuario autenticado (§4.2)."""
    result = await db.execute(
        select(UserDevice)
        .where(UserDevice.user_id == current_user.id)
        .order_by(UserDevice.last_seen_at.desc())
    )
    return [DeviceResponse.model_validate(d) for d in result.scalars().all()]


@router.delete(
    "/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dar de baja un dispositivo",
)
async def delete_device(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Elimina el registro del dispositivo y detiene los push hacia él (§4.3).
    Solo se pueden eliminar dispositivos propios.
    """
    device = await db.get(UserDevice, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispositivo no encontrado")
    if str(device.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puede eliminar dispositivos de otro usuario",
        )
    await db.delete(device)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
