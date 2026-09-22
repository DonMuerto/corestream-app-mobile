"""
Unit tests for the invitation email builder. smtplib is mocked — no real
network or SMTP credentials are touched.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services import email_service


@pytest.mark.asyncio
async def test_no_smtp_configured_is_noop():
    with patch("app.services.email_service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(SMTP_HOST="", MAIL_FROM="")
        sent = await email_service.send_invitation_email(
            to_email="dev@example.com", role="DEVELOPER", invite_url="https://x/invite/tok"
        )
    assert sent is False


def test_message_has_date_and_message_id():
    """
    Date and Message-ID are not added by EmailMessage on its own. Missing
    them is a spam signal for strict filters that can accept-then-drop a
    message with no error on our side (the actual production bug).
    """
    settings = MagicMock(
        SMTP_HOST="smtp.example.com",
        SMTP_PORT=587,
        SMTP_USER="user@example.com",
        SMTP_PASSWORD="secret",
        SMTP_USE_SSL=False,
        MAIL_FROM="welcome@example.com",
        MAIL_FROM_NAME="CoreStream",
    )

    sent_messages = []

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            pass

        def login(self, *args, **kwargs):
            pass

        def send_message(self, message):
            sent_messages.append(message)

    with patch("app.services.email_service.get_settings", return_value=settings), \
            patch("app.services.email_service.smtplib.SMTP", FakeSMTP):
        email_service._send_sync("dev@example.com", "Subject", "<p>html</p>", "text")

    assert len(sent_messages) == 1
    message = sent_messages[0]
    assert message["Date"] is not None
    assert message["Message-ID"] is not None
    assert "example.com" in message["Message-ID"]
