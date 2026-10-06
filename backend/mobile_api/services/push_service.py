"""
Envío de notificaciones push con Firebase Cloud Messaging (§9.2).

Modo de operación:
    - Con la variable de entorno FIREBASE_CREDENTIALS_JSON (ruta a un archivo
      de credenciales de cuenta de servicio, o el JSON inline), inicializa
      firebase-admin y envía push reales.
    - Sin credenciales, o si firebase-admin no está instalado, entra en MODO
      SIMULADO: registra el envío en el log y no falla. El backend arranca y
      se prueba sin cuenta de Firebase.

Integración con el sistema existente:
    `PushService.notify_user(...)` es el punto único que usan los routers
    nuevos: persiste la notificación in-app (modelo Notification), la publica
    en Redis para el WebSocket (canal notifications:{user_id}, igual que
    NotificationService) y envía el push FCM como mejor esfuerzo,
    respetando las preferencias y el horario de silencio del usuario.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, User
from app.models.notification import NotificationType
from app.redis_client import publish_message
from mobile_api.models.device import UserDevice, NotificationPreference

logger = logging.getLogger("mobile_api.push")

# Mapa tipo de notificación -> campo booleano de preferencias
_PREF_FIELD = {
    "ASSIGNMENT": "ticket_assigned",
    "REDIRECT": "ticket_assigned",
    "QUESTION": "question_asked",
    "COMPLETION": "ticket_completed",
    "INCIDENT_REPORTED": "incident_reported",
    "INCIDENT_ASSIGNED": "incident_reported",
    "SYSTEM": None,  # SYSTEM se envía siempre que push_enabled sea True
}

_firebase_app = None
_firebase_checked = False


def _init_firebase():
    """Inicializa firebase-admin una sola vez; None => modo simulado."""
    global _firebase_app, _firebase_checked
    if _firebase_checked:
        return _firebase_app
    _firebase_checked = True

    creds = os.environ.get("FIREBASE_CREDENTIALS_JSON", "").strip()
    if not creds:
        logger.warning("FIREBASE_CREDENTIALS_JSON no configurada: push en MODO SIMULADO")
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials

        if creds.startswith("{"):
            cred = credentials.Certificate(json.loads(creds))
        else:
            cred = credentials.Certificate(creds)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("firebase-admin inicializado para envíos push")
    except ImportError:
        logger.warning("firebase-admin no instalado: push en MODO SIMULADO")
    except Exception as exc:  # credenciales corruptas, etc.
        logger.error("No se pudo inicializar firebase-admin (%s): MODO SIMULADO", exc)
    return _firebase_app


def _in_quiet_hours(prefs: Optional[NotificationPreference], now: Optional[datetime] = None) -> bool:
    """True si la hora actual cae dentro del horario de silencio del usuario."""
    if prefs is None or not prefs.quiet_hours_start or not prefs.quiet_hours_end:
        return False
    now = now or datetime.now()
    current = now.strftime("%H:%M")
    start, end = prefs.quiet_hours_start, prefs.quiet_hours_end
    if start <= end:
        return start <= current < end
    # Rango que cruza medianoche (ej. 22:00 -> 07:00)
    return current >= start or current < end


class PushService:
    """Fachada de notificaciones para los routers del módulo móvil."""

    # ------------------------------------------------------------ envío FCM

    @staticmethod
    async def send_push_to_user(
        db: AsyncSession,
        user_id: str,
        title: str,
        body: str,
        data: Optional[dict[str, str]] = None,
        notification_type: str = "SYSTEM",
    ) -> int:
        """
        Envía un push a todos los dispositivos activos del usuario.

        Respeta push_enabled, el booleano por tipo y el horario de silencio.

        Returns:
            int: Número de dispositivos a los que se envió (o simuló) el push.
        """
        prefs = await db.get(NotificationPreference, user_id)
        if prefs is not None:
            if not prefs.push_enabled:
                return 0
            field = _PREF_FIELD.get(notification_type)
            if field and not getattr(prefs, field, True):
                return 0
        if _in_quiet_hours(prefs):
            logger.info("Push a %s omitido por horario de silencio", user_id)
            return 0

        result = await db.execute(
            select(UserDevice).where(
                UserDevice.user_id == user_id, UserDevice.is_active == True  # noqa: E712
            )
        )
        devices = list(result.scalars().all())
        if not devices:
            return 0

        payload = {k: str(v) for k, v in (data or {}).items() if v is not None}
        app_fb = _init_firebase()
        if app_fb is None:
            for d in devices:
                logger.info(
                    "[PUSH SIMULADO] user=%s device=%s platform=%s title=%r body=%r data=%s",
                    user_id, d.id, d.platform, title, body, payload,
                )
            return len(devices)

        from firebase_admin import messaging

        message = messaging.MulticastMessage(
            tokens=[d.fcm_token for d in devices],
            notification=messaging.Notification(title=title, body=body),
            data=payload,
            android=messaging.AndroidConfig(priority="high"),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(aps=messaging.Aps(sound="default"))
            ),
        )
        # firebase-admin es síncrono: se despacha en un hilo para no bloquear
        response = await asyncio.to_thread(messaging.send_each_for_multicast, message)

        sent = 0
        for device, item in zip(devices, response.responses):
            if item.success:
                sent += 1
                continue
            code = getattr(getattr(item.exception, "code", None), "name", "") or str(item.exception)
            if "UNREGISTERED" in code.upper() or "INVALID_ARGUMENT" in code.upper():
                device.is_active = False  # token muerto: no reintentar (§9.2)
                logger.info("Dispositivo %s desactivado (token FCM inválido)", device.id)
            else:
                logger.warning("Fallo de push al dispositivo %s: %s", device.id, code)
        await db.commit()
        return sent

    # ------------------------------------------------- notificación completa

    @staticmethod
    async def notify_user(
        db: AsyncSession,
        user_id: str,
        title: str,
        message: str,
        notification_type: str,
        ticket_id: Optional[str] = None,
        incident_id: Optional[str] = None,
    ) -> Notification:
        """
        Crea la notificación in-app, la publica por WebSocket y envía el push.

        Nota sobre tipos de incidencias (§7.2): mientras no se aplique el
        parche que añade INCIDENT_REPORTED / INCIDENT_ASSIGNED al enum
        NotificationType, esos tipos se persisten como SYSTEM (el push y el
        payload conservan el tipo real para el deep link de la app).
        """
        valid_types = {t.value for t in NotificationType}
        persisted_type = notification_type if notification_type in valid_types else "SYSTEM"

        notification = Notification(
            user_id=user_id,
            title=title[:200],
            message=message[:1000],
            type=persisted_type,
            ticket_id=ticket_id,
        )
        # incident_id existe tras la migración + parche §7.2
        if incident_id is not None and hasattr(Notification, "incident_id"):
            notification.incident_id = incident_id

        db.add(notification)
        await db.commit()
        await db.refresh(notification)

        # 1) Tiempo real (WebSocket) por el mismo canal que usa la web
        try:
            await publish_message(
                f"notifications:{user_id}",
                {
                    "id": str(notification.id),
                    "title": title,
                    "message": message,
                    "type": notification_type,
                    "ticket_id": str(ticket_id) if ticket_id else None,
                    "incident_id": str(incident_id) if incident_id else None,
                    "created_at": notification.created_at.isoformat(),
                },
            )
        except Exception as exc:  # Redis caído no debe romper la petición
            logger.warning("No se pudo publicar la notificación en Redis: %s", exc)

        # 2) Push FCM: mejor esfuerzo — un fallo aquí nunca revierte la
        #    operación de negocio que originó la notificación
        data = {
            "notification_id": str(notification.id),
            "type": notification_type,
        }
        if ticket_id:
            data["ticket_id"] = str(ticket_id)
        if incident_id:
            data["incident_id"] = str(incident_id)

        try:
            await PushService.send_push_to_user(
                db, str(user_id), title, message, data, notification_type
            )
        except Exception as exc:  # el push nunca revierte la operación de negocio
            logger.error("Error enviando push a %s: %s", user_id, exc)

        return notification
