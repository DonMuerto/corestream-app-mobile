"""
WebSocket de notificaciones autenticado por JWT (§7.1).

Sustituye a /ws/notifications/{user_id}, que identifica al usuario por un id
en la ruta sin verificar el token (cualquier cliente podría suscribirse a las
notificaciones de otro usuario). Este endpoint:

    - Acepta el access token como query param:  /ws/mobile/notifications?token=<jwt>
    - Valida firma y expiración en el handshake con la misma lógica que
      get_current_user y deriva el user_id del claim `sub`.
    - Cierra con código 4401 si el token es inválido/expirado y 4403 si el
      usuario está inactivo.
    - Se suscribe al mismo canal Redis que usa la web (notifications:{user_id}),
      por lo que las notificaciones existentes llegan sin cambios.

El WebSocket antiguo debe marcarse como obsoleto (ver patches/).
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.database import get_db
from app.middleware.auth import verify_token
from app.models import User
from app.redis_client import subscribe_channel

logger = logging.getLogger("mobile_api.ws")

router = APIRouter(tags=["WebSocket móvil"])

WS_INVALID_TOKEN = 4401   # Token inválido o expirado
WS_INACTIVE_USER = 4403   # Usuario inactivo


@router.websocket("/ws/mobile/notifications")
async def websocket_mobile_notifications(
    websocket: WebSocket,
    token: str = Query(..., description="Access token JWT"),
):
    """Canal de notificaciones en tiempo real para la app móvil (§7.1)."""
    # --- Handshake: validar JWT antes de aceptar ---
    try:
        payload = verify_token(token)
        user_id = str(payload.sub)
    except Exception:
        await websocket.accept()
        await websocket.close(code=WS_INVALID_TOKEN, reason="Token inválido o expirado")
        return

    # Verificar que el usuario existe y está activo
    async for db in get_db():
        user = await db.get(User, user_id)
        if user is None or not user.is_active:
            await websocket.accept()
            await websocket.close(code=WS_INACTIVE_USER, reason="Usuario inactivo")
            return
        break

    await websocket.accept()
    logger.info("WebSocket móvil conectado: user=%s", user_id)

    pubsub = None
    try:
        pubsub = await subscribe_channel(f"notifications:{user_id}")

        async def forward_notifications():
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                data = message.get("data")
                if isinstance(data, (bytes, bytearray)):
                    data = data.decode("utf-8")
                await websocket.send_text(data if isinstance(data, str) else json.dumps(data))

        async def keepalive():
            # Ping de aplicación cada 30 s; también detecta desconexión del cliente
            while True:
                await asyncio.sleep(30)
                await websocket.send_text(json.dumps({"type": "ping"}))

        forward_task = asyncio.create_task(forward_notifications())
        ping_task = asyncio.create_task(keepalive())
        done, pending = await asyncio.wait(
            {forward_task, ping_task}, return_when=asyncio.FIRST_EXCEPTION
        )
        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        logger.info("WebSocket móvil desconectado: user=%s", user_id)
    except Exception as exc:
        logger.warning("WebSocket móvil cerrado con error (user=%s): %s", user_id, exc)
    finally:
        if pubsub is not None:
            try:
                await pubsub.unsubscribe()
                await pubsub.close()
            except Exception:
                pass
