"""Regression coverage for failures found in the hosted mobile QA."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.models import Ticket, TicketEvent, TicketStatus
from app.models.notification import NotificationType
from app.routers.tickets import _set_ticket_archived, control_work_timer
from app.schemas.notification import NotificationResponse
from mobile_api.schemas.mobile import AttentionItem, UserBrief
from mobile_api.services.permission_service import compute_ticket_permissions


@pytest.mark.parametrize("kind", list(NotificationType))
def test_every_stored_notification_type_is_serializable(kind):
    incident_id = uuid4()
    obj = SimpleNamespace(id=uuid4(), user_id=uuid4(), title="QA", message="QA",
        type=kind, is_read=False, ticket_id=None, incident_id=incident_id,
        read_at=None, created_at=datetime.now(timezone.utc))
    response = NotificationResponse.model_validate(obj)
    assert response.type == kind.value
    assert response.incident_id == incident_id


def test_unknown_notification_type_is_still_rejected():
    with pytest.raises(ValidationError):
        NotificationResponse(id=uuid4(), user_id=uuid4(), title="QA", message="QA",
                             type="BOGUS", is_read=False, created_at=datetime.now(timezone.utc))


def test_attention_keeps_assignee_identity():
    user = UserBrief(id=uuid4(), full_name="Diego Ramos", role="DEVELOPER")
    item = AttentionItem(kind="TICKET", id=uuid4(), title="QA", app_name="QA",
                         status="BLOCKED_QUESTION", assignee_name=user.full_name, assignee=user)
    assert item.model_dump(mode="json")["assignee"]["id"] == str(user.id)


def test_archived_permissions_and_manual_timer_permissions():
    p = compute_ticket_permissions("ADMIN", "a", "IN_PROGRESS", "d", archived=True)
    assert p["can_restore"] and sum(p.values()) == 1
    assert not any(compute_ticket_permissions("DEVELOPER", "d", "IN_PROGRESS", "d", archived=True).values())
    p = compute_ticket_permissions("DEVELOPER", "d", "IN_PROGRESS", "d", timer_running=True)
    assert p["can_pause"] and not p["can_resume_timer"]
    p = compute_ticket_permissions("DEVELOPER", "d", "IN_PROGRESS", "d")
    assert p["can_resume_timer"] and not p["can_pause"]


async def test_archive_hides_ticket_without_losing_subtasks_or_events(db_session, sample_ticket, sample_user):
    from app.models import Subtask

    sub = Subtask(ticket_id=sample_ticket.id, title="Keep me", is_completed=True, order_index=0)
    db_session.add(sub)
    await db_session.commit()
    with patch("app.services.timer_service.get_cached_value", new=AsyncMock(return_value=None)), \
         patch("app.services.timer_service.delete_cached_value", new=AsyncMock()), \
         patch("app.routers.tickets._publish_ticket_status", new=AsyncMock()):
        result = await _set_ticket_archived(sample_ticket.id, sample_user, db_session, True)
        assert result.archived_at is not None and result.timer_started_at is None
        assert result.archived_by_id == sample_user.id
        assert not (await db_session.execute(select(Ticket))).scalars().all()
        assert (await db_session.execute(select(func.count(Ticket.id)))).scalar() == 0
        assert (await db_session.execute(select(Subtask))).scalars().one().is_completed
        events = (await db_session.execute(select(TicketEvent))).scalars().all()
        assert [e.detail["action"] for e in events] == ["ARCHIVED"]
        await _set_ticket_archived(sample_ticket.id, sample_user, db_session, True)
        assert (await db_session.execute(select(func.count(TicketEvent.id)))).scalar() == 1
        result = await _set_ticket_archived(sample_ticket.id, sample_user, db_session, False)
        assert result.archived_at is None
        assert (await db_session.execute(select(func.count(Ticket.id)))).scalar() == 1
        events = (await db_session.execute(select(TicketEvent).order_by(TicketEvent.created_at))).scalars().all()
        assert [e.detail["action"] for e in events] == ["ARCHIVED", "RESTORED"]


async def test_manual_pause_resume_is_idempotent_and_does_not_block(db_session, sample_ticket, sample_user, sample_role):
    sample_role.name = "DEVELOPER"
    sample_user.role = sample_role
    sample_ticket.status = TicketStatus.IN_PROGRESS
    sample_ticket.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=30)
    await db_session.commit()
    with patch("app.services.timer_service.get_cached_value", new=AsyncMock(return_value=None)), \
         patch("app.services.timer_service.delete_cached_value", new=AsyncMock()), \
         patch("app.routers.tickets._publish_ticket_status", new=AsyncMock()):
        ticket = await control_work_timer(sample_ticket.id, "pause", sample_user, db_session)
        saved = ticket.time_spent_seconds
        assert saved >= 3630 and ticket.timer_started_at is None
        assert ticket.status == TicketStatus.IN_PROGRESS and ticket.blocked_at is None
        await control_work_timer(ticket.id, "pause", sample_user, db_session)
        assert ticket.time_spent_seconds == saved
        await control_work_timer(ticket.id, "resume", sample_user, db_session)
        start = ticket.timer_started_at
        await control_work_timer(ticket.id, "resume", sample_user, db_session)
        assert ticket.timer_started_at == start and ticket.time_spent_seconds == saved
        assert (await db_session.execute(select(func.count(TicketEvent.id)))).scalar() == 2
