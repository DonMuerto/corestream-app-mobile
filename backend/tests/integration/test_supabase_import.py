import argparse
import json

from sqlalchemy import select, text

from app.database import get_session_maker
from app.models import Application, Ticket, User
from scripts import import_supabase_demo
from tests.test_supabase_import import snapshot_fixture


async def test_import_transaction_and_idempotence(client, tmp_path, monkeypatch):
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(snapshot_fixture()))
    args = argparse.Namespace(snapshot=str(snapshot), credentials=str(tmp_path / "accounts.json"),
                              apply=True, enable_demo_users=True)
    # Integration fixtures target only the disposable corestream_test database.
    monkeypatch.setattr(import_supabase_demo, "validate_destination", lambda url, apply: None)
    async with get_session_maker()() as db:
        original_users = len((await db.execute(select(User))).scalars().all())
    await import_supabase_demo.run(args)
    # dispose_engine is intentional; reconfigure explicitly for the test session.
    from app.config import get_settings
    from app.database import configure_engine
    configure_engine(get_settings().DATABASE_URL)
    async with get_session_maker()() as db:
        assert len((await db.execute(select(User))).scalars().all()) == original_users + 1
        assert len((await db.execute(select(Ticket))).scalars().all()) == 1
        assert (await db.execute(text("SELECT count(*) FROM migration_archive.supabase_records"))).scalar() == 7
        ticket = (await db.execute(select(Ticket))).scalar_one()
        ticket.title = "Newer target change"
        await db.commit()
    await import_supabase_demo.run(args)
    configure_engine(get_settings().DATABASE_URL)
    async with get_session_maker()() as db:
        assert (await db.execute(select(Ticket))).scalar_one().title == "Newer target change"
        assert len((await db.execute(select(Application))).scalars().all()) == 1
    assert len(json.loads((tmp_path / "accounts.json").read_text())["accounts"]) == 1
