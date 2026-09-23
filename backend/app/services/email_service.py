"""
Email sending service (plan 3.7.1).

Used by the invitation flow (app/routers/invitations.py) to send the
invitee their invite link, and by self-service password reset
(app/routers/auth.py) to send the recovery link.

Uses smtplib (stdlib) instead of adding a new dependency — sending is
occasional (one invitation every so often), not enough to justify a
dedicated async client. smtplib blocks, so it runs in a threadpool via
asyncio.to_thread to avoid blocking FastAPI's event loop.

If SMTP_HOST isn't configured, sending is a noop and returns False — so
the dev environment keeps working without SMTP.
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
    Never raises on send failure — only logs it — so an SMTP problem never
    breaks the operation that triggered it (the invitation or reset token
    are already saved regardless of the email).

    Returns True if sent, False if SMTP isn't configured or it failed.
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
