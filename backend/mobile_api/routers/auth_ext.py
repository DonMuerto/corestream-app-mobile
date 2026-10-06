"""
Extensión del router de autenticación: logout con revocación (§4.6).

Prefijo: /auth (conviven con el router existente sin colisión de rutas).
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.schemas import TokenPayload
from mobile_api.models.device import UserDevice
from mobile_api.schemas.auth_ext import LogoutRequest
from mobile_api.services.token_blacklist import revoke_refresh_token

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar sesión (revocar refresh token)",
)
async def logout(
    payload: LogoutRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Cierra la sesión del dispositivo actual (§4.6):

        1. Revoca el refresh token (lista de revocados en Redis con TTL
           igual a su caducidad).
        2. Si se envía fcm_token, desactiva ese dispositivo para push.

    Nota: para que la revocación sea efectiva, POST /auth/refresh debe
    consultar `is_refresh_token_revoked` (parche §4.6 en patches/).
    """
    try:
        await revoke_refresh_token(payload.refresh_token, current_user.sub)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if payload.fcm_token:
        result = await db.execute(
            select(UserDevice).where(
                UserDevice.fcm_token == payload.fcm_token,
                UserDevice.user_id == current_user.sub,
            )
        )
        device = result.scalar_one_or_none()
        if device is not None:
            device.is_active = False
            await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
