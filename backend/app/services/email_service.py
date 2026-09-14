"""
Servicio de envío de correo (plan 3.7.1).

Usado hoy únicamente por el flujo de invitaciones (app/routers/invitations.py)
para mandarle al invitado el link de invitación por correo, además de que el
admin lo pueda seguir copiando a mano desde la UI (ver InvitationResponse).

Usa smtplib (stdlib) en vez de sumar una dependencia nueva — el envío es
puntual (una invitación cada tanto), no justifica un cliente async dedicado.
smtplib bloquea, así que se corre en threadpool vía asyncio.to_thread para no
trabar el event loop de FastAPI.

Si SMTP_HOST no está configurado, send_invitation_email no hace nada (noop)
y devuelve False — así el entorno de desarrollo sigue funcionando sin SMTP,
igual que antes de este cambio.
"""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger("corestream.email")


def _send_sync(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    settings = get_settings()

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
    message["To"] = to_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    if settings.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
    else:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)


async def send_invitation_email(*, to_email: str, role: str, invite_url: str) -> bool:
    """
    Manda el correo de invitación. No lanza excepción si falla el envío —
    solo la loguea — para que un problema de SMTP nunca tumbe la creación de
    la invitación (el token ya quedó guardado y el admin lo puede compartir
    a mano como fallback, igual que en el diseño original).

    Devuelve True si se mandó, False si SMTP no está configurado o falló.
    """
    settings = get_settings()
    if not settings.SMTP_HOST or not settings.MAIL_FROM:
        logger.info("SMTP no configurado — no se envía correo de invitación a %s", to_email)
        return False

    subject = "Invitación a CoreStream"
    text_body = (
        f"Fuiste invitado a CoreStream con el rol {role}.\n\n"
        f"Aceptá la invitación en este link (válido por 7 días):\n{invite_url}\n"
    )
    html_body = f"""
    <p>Fuiste invitado a <strong>CoreStream</strong> con el rol <strong>{role}</strong>.</p>
    <p><a href="{invite_url}">Aceptá la invitación acá</a> (el link es válido por 7 días).</p>
    <p>Si el link no funciona, copiá y pegá esta URL en el navegador:<br>{invite_url}</p>
    """

    try:
        await asyncio.to_thread(_send_sync, to_email, subject, html_body, text_body)
        return True
    except Exception:
        logger.exception("Falló el envío del correo de invitación a %s", to_email)
        return False
