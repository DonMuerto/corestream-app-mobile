"""Read-only reconciliation: exported rows -> Neon archive -> official API.

Never prints credentials. Optional --ui-title checks a ticket created in Flutter.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from sqlalchemy import select, text

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main(args):
    from app.database import dispose_engine, get_session_maker
    from app.models import Base, Ticket, TicketEvent, User
    from app.services.auth_service import AuthService

    snapshot = json.loads(await asyncio.to_thread((BACKEND / ".supabase-import.local.json").read_text, encoding="utf-8"))
    accounts = json.loads(await asyncio.to_thread((BACKEND / ".supabase-accounts.local.json").read_text, encoding="utf-8"))["accounts"]
    async with get_session_maker()() as db:
        rows = (await db.execute(text("SELECT * FROM migration_archive.supabase_records WHERE source_project=:p"),
                                 {"p": snapshot["source_project"]})).mappings().all()
        archive = {(r["source_table"], r["source_id"]): r for r in rows}
        assert len(rows) == sum(map(len, snapshot["tables"].values()))
        for source_table, source_rows in snapshot["tables"].items():
            for original in source_rows:
                record = archive[(source_table, str(original["id"]))]
                assert record["payload"] == original, f"Changed archive payload: {source_table}"
                if record["target_table"]:
                    table = Base.metadata.tables[record["target_table"]]
                    persisted = (await db.execute(select(table).where(table.c.id == record["target_id"]))).mappings().one()
                    if source_table == "tickets":
                        assert persisted["title"] == original["title"]
                        assert persisted["description"] == original["description"]
                        assert persisted["time_spent_seconds"] == original["spent_seconds"]
                        assert persisted["blocked_time_seconds"] == original["blocked_seconds"]
                        assert persisted["pr_link"] == original["pr_link"]
                        assert persisted["assignee_id"] == (archive[("demo_users", original["assignee_id"])]["target_id"] if original["assignee_id"] else None)
                        assert persisted["epic_id"] == archive[("epics", original["epic_id"])]["target_id"]
                        assert persisted["timer_started_at"] is None
                elif source_table == "tickets":
                    assert original["deleted_at"] is not None
        for account in accounts:
            user_id = archive[("demo_users", account["source_id"])]["target_id"]
            user = await db.get(User, user_id)
            assert user.is_active == account["is_active"]
            assert AuthService.verify_password(account["password"], user.hashed_password)
        print(f"Archivo reconciliado sin pérdida: {len(rows)} filas originales, incluidos archivados.")
        print("Tickets: títulos, descripciones, responsables, épicas, PR y tiempos coinciden con el origen.")
        if args.ui_title:
            assert args.ui_title.startswith("Prueba Flutter UI ")
            ticket = (await db.execute(select(Ticket).where(Ticket.title == args.ui_title))).scalar_one()
            assert ticket.created_by_id is not None
            events = (await db.execute(select(TicketEvent).where(TicketEvent.ticket_id == ticket.id))).scalars().all()
            print("Ticket creado en la web confirmado en Neon: " + ticket.title)
            print(f"Estado {ticket.status.value}; prioridad {ticket.priority.value}; eventos {len(events)}; responsable {ticket.assignee_id}")
    base = "https://corestream-app-base-grupo1.vercel.app/api"
    async with httpx.AsyncClient(base_url=base, timeout=45) as client:
        health = await client.get("/health")
        assert health.status_code == 200 and health.json()["checks"] == {"database": "ok", "redis": "ok"}
        print("HTTPS de Flutter -> FastAPI -> PostgreSQL + Redis: OK")
        for account in accounts:
            if not account["is_active"]:
                continue
            login = await client.post("/auth/login", json={"email": account["email"], "password": account["password"]})
            assert login.status_code == 200, f"Login {account['source_id']}: HTTP {login.status_code}"
            client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
            me = await client.get("/auth/me")
            assert me.status_code == 200 and me.json()["role"] == account["role"]
            dashboard = await client.get("/mobile/dashboard")
            assert dashboard.status_code == 200, f"Dashboard HTTP {dashboard.status_code}"
            print(f"Login + dashboard autenticados: {account['full_name']} ({account['role']}) OK")
            await client.post("/auth/logout", json={})
            client.headers.pop("Authorization", None)
    await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui-title")
    args = parser.parse_args()
    load_dotenv(BACKEND / ".env.vercel.local", override=True)
    try:
        asyncio.run(main(args))
    except Exception as exc:
        # Do not print network exceptions, DSNs, tokens or password hashes.
        print(f"Verificación incompleta ({type(exc).__name__}).")
        raise SystemExit(1) from None
