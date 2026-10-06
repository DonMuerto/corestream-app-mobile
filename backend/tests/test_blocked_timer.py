from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.timer_service import TimerService


def test_block_start_is_idempotent():
    now = datetime(2026, 10, 6, tzinfo=timezone.utc)
    ticket = SimpleNamespace(blocked_at=None, blocked_time_seconds=20)
    TimerService.begin_blocked_period(ticket, now)
    TimerService.begin_blocked_period(ticket, now + timedelta(seconds=10))
    assert ticket.blocked_at == now
    assert ticket.blocked_time_seconds == 20


def test_block_end_accumulates_exactly_once():
    now = datetime(2026, 10, 6, tzinfo=timezone.utc)
    ticket = SimpleNamespace(blocked_at=now - timedelta(seconds=30), blocked_time_seconds=20)
    assert TimerService.finish_blocked_period(ticket, now) == 30
    assert ticket.blocked_time_seconds == 50
    assert ticket.blocked_at is None
    assert TimerService.finish_blocked_period(ticket, now + timedelta(seconds=10)) == 0
    assert ticket.blocked_time_seconds == 50


def test_legacy_naive_utc_timestamp_is_supported():
    now = datetime(2026, 10, 6, tzinfo=timezone.utc)
    ticket = SimpleNamespace(blocked_at=now.replace(tzinfo=None) - timedelta(seconds=30), blocked_time_seconds=0)
    assert TimerService.finish_blocked_period(ticket, now) == 30


def test_future_timestamp_never_subtracts_accumulated_time():
    now = datetime(2026, 10, 6, tzinfo=timezone.utc)
    ticket = SimpleNamespace(blocked_at=now + timedelta(seconds=10), blocked_time_seconds=20)
    assert TimerService.finish_blocked_period(ticket, now) == 0
    assert ticket.blocked_time_seconds == 20
