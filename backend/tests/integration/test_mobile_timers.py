from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy import select

from app.database import get_session_maker
from app.models import Ticket, TicketEvent, TicketStatus

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_question_and_resolution_preserve_separate_timers(client, dev_headers, leader_headers, ticket):
    ticket_id = ticket['id']
    res = await client.post(f'/api/tickets/{ticket_id}/start', headers=dev_headers)
    assert res.status_code == 200
    async with get_session_maker()() as db:
        saved = await db.get(Ticket, UUID(ticket_id))
        saved.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=20)
        await db.commit()
    res = await client.post(f'/api/tickets/{ticket_id}/question', headers=dev_headers,
                            json={'question_text': 'Confirmar medición de los tiempos'})
    assert res.status_code == 200
    detail = (await client.get(f'/api/mobile/tickets/{ticket_id}/detail', headers=dev_headers)).json()
    assert detail['timer']['blocked_started_at'] is not None
    assert detail['timer']['is_running'] is False
    async with get_session_maker()() as db:
        saved = await db.get(Ticket, UUID(ticket_id))
        assert saved.timer_started_at is None
        assert saved.time_spent_seconds >= 20
        work_before = saved.time_spent_seconds
        saved.blocked_at = datetime.now(timezone.utc) - timedelta(seconds=30)
        await db.commit()
    res = await client.post(f'/api/tickets/{ticket_id}/resolve-question', headers=leader_headers,
                            json={'resolution': 'Verificado en PostgreSQL'})
    assert res.status_code == 200
    async with get_session_maker()() as db:
        saved = await db.get(Ticket, UUID(ticket_id))
        assert saved.status == TicketStatus.IN_PROGRESS
        assert saved.time_spent_seconds == work_before
        assert saved.blocked_time_seconds >= 30
        assert saved.blocked_at is None
        assert saved.timer_started_at is not None


@pytest.mark.parametrize('blocked', [False, True])
async def test_reassign_preserves_time_and_audits_recipient(client, dev_headers, leader_headers,
                                                          ticket, dev_id, dev2_id, blocked):
    ticket_id = ticket['id']
    async with get_session_maker()() as db:
        saved = await db.get(Ticket, UUID(ticket_id))
        saved.status = TicketStatus.BLOCKED_QUESTION if blocked else TicketStatus.IN_PROGRESS
        saved.time_spent_seconds = 10
        saved.blocked_time_seconds = 15
        if blocked:
            saved.blocked_at = datetime.now(timezone.utc) - timedelta(seconds=30)
        else:
            saved.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=20)
        await db.commit()
    # Re-selecting the same recipient must not reset their state or clock.
    same = await client.put(f'/api/tickets/{ticket_id}', headers=leader_headers,
                            json={'assignee_id': dev_id})
    assert same.status_code == 200
    assert same.json()['status'] == ('BLOCKED_QUESTION' if blocked else 'IN_PROGRESS')
    res = await client.put(f'/api/tickets/{ticket_id}', headers=leader_headers,
                           json={'assignee_id': dev2_id})
    assert res.status_code == 200
    async with get_session_maker()() as db:
        saved = await db.get(Ticket, UUID(ticket_id))
        assert saved.assignee_id == UUID(dev2_id)
        assert saved.status == TicketStatus.TODO
        assert saved.timer_started_at is None and saved.blocked_at is None
        if blocked:
            assert saved.blocked_time_seconds >= 45
            assert saved.time_spent_seconds == 10
        else:
            assert saved.time_spent_seconds >= 30
            assert saved.blocked_time_seconds == 15
        events = (await db.execute(select(TicketEvent).where(TicketEvent.ticket_id == saved.id))).scalars().all()
        assert any(e.detail.get('from_user_id') == dev_id and e.detail.get('to_user_id') == dev2_id for e in events)
