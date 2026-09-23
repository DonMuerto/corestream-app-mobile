"""
Servicio de envío de correo (plan 3.7.1).

Usado por el flujo de invitaciones (app/routers/invitations.py) para mandarle
al invitado el link de invitación, y por el reset de contraseña de
autoservicio (app/routers/auth.py) para mandar el link de recuperación.

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
from email.utils import formatdate, make_msgid

from app.config import get_settings

logger = logging.getLogger("corestream.email")


def _send_sync(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    settings = get_settings()

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
    message["To"] = to_email
    # EmailMessage does not set these on its own. Missing Date/Message-ID is a
    # spam signal for strict filters (Google/Microsoft, common on university
    # domains) — they can accept the message at our SMTP hop and drop it
    # downstream with no error on our side.
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=settings.MAIL_FROM.split("@")[-1])
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


async def _send(*, to_email: str, subject: str, html_body: str, text_body: str, log_label: str) -> bool:
    """
    No lanza excepción si falla el envío — solo la loguea — para que un
    problema de SMTP nunca tumbe la operación que lo dispara (la invitación
    o el token de reset ya quedaron guardados independientemente del correo).

    Devuelve True si se mandó, False si SMTP no está configurado o falló.
    """
    settings = get_settings()
    if not settings.SMTP_HOST or not settings.MAIL_FROM:
        logger.info("SMTP no configurado — no se envía %s a %s", log_label, to_email)
        return False

    try:
        await asyncio.to_thread(_send_sync, to_email, subject, html_body, text_body)
        return True
    except Exception:
        logger.exception("Falló el envío de %s a %s", log_label, to_email)
        return False


async def send_invitation_email(*, to_email: str, role: str, invite_url: str) -> bool:
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
    return await _send(
        to_email=to_email, subject=subject, html_body=html_body, text_body=text_body,
        log_label="correo de invitación",
    )


async def send_password_reset_email(*, to_email: str, reset_url: str) -> bool:
    subject = "Restablecer contraseña de CoreStream"
    text_body = (
        "Pediste restablecer tu contraseña en CoreStream.\n\n"
        f"Elegí una nueva acá (válido por 1 hora):\n{reset_url}\n\n"
        "Si no fuiste vos, ignorá este correo — tu contraseña actual sigue funcionando."
    )
    html_body = f"""
    <p>Pediste restablecer tu contraseña en <strong>CoreStream</strong>.</p>
    <p><a href="{reset_url}">Elegí una nueva acá</a> (el link es válido por 1 hora).</p>
    <p>Si no fuiste vos, ignorá este correo — tu contraseña actual sigue funcionando.</p>
    """
    return await _send(
        to_email=to_email, subject=subject, html_body=html_body, text_body=text_body,
        log_label="correo de reset de contraseña",
    )
