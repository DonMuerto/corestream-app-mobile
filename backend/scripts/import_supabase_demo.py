"""Import a read-only Supabase snapshot into the official PostgreSQL schema.

Default is dry-run. --apply is atomic and insert-only. Archived rows and fields
without an official equivalent remain losslessly in the private archive.
No source database access, open RLS, mock repository or public registration.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
SOURCE_PROJECT = "frxqettffjbnuncugtuu"
TABLES = ("demo_users", "applications", "epics", "tickets", "ticket_subtasks",
          "ticket_events", "demo_incidents", "demo_incident_comments", "demo_notifications")
TARGETS = dict(zip(TABLES, ("users", "applications", "epics", "tickets", "subtasks",
                           "ticket_events", "incidents", None, "notifications"), strict=True))
EVENTS = {"CREATED": "CREATED", "ASSIGNED": "ASSIGNED", "STATUS": "STATUS_CHANGED",
          "COMMENT": "COMMENT", "QUESTION": "QUESTION_RAISED", "RESOLVED": "QUESTION_RESOLVED",
          "REDIRECTED": "REDIRECTED", "COMPLETED": "COMPLETED"}
INCIDENT_STATUS = {"OPEN": "REPORTED", "IN_PROGRESS": "INVESTIGATING",
                   "UNDER_REVIEW": "INVESTIGATING", "RESOLVED": "RESOLVED"}
SEVERITY = {"CRITICAL": "P1", "HIGH": "P2", "MEDIUM": "P3", "LOW": "P3"}
NOTIFICATIONS = {"ASSIGNMENT": "TICKET_ASSIGNED", "QUESTION": "QUESTION_RAISED",
                 "INCIDENT": "INCIDENT_REPORTED", "SYSTEM": "SYSTEM",
                 "REDIRECT": "TICKET_REDIRECTED", "COMPLETION": "TICKET_COMPLETED"}


def dt(value):
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Snapshot timestamps must include timezone")
    return parsed


def prepare(snapshot):
    if snapshot["source_project"] != SOURCE_PROJECT:
        raise ValueError("Unexpected source project")
    tables = snapshot["tables"]
    if set(tables) != set(TABLES):
        raise ValueError("Export must contain every expected public source table")
    ids = {t: {str(r["id"]): r for r in tables[t]} for t in TABLES}
    if any(len(ids[t]) != len(tables[t]) for t in TABLES):
        raise ValueError("Duplicate source identity")
    references = {
        "epics": [("application_id", "applications")],
        "tickets": [("epic_id", "epics"), ("assignee_id", "demo_users"),
                    ("created_by_id", "demo_users"), ("deleted_by_id", "demo_users")],
        "ticket_subtasks": [("ticket_id", "tickets")],
        "ticket_events": [("ticket_id", "tickets"), ("user_id", "demo_users"), ("to_user_id", "demo_users")],
        "demo_incidents": [("application_id", "applications"), ("reporter_id", "demo_users"), ("assignee_id", "demo_users")],
        "demo_incident_comments": [("incident_id", "demo_incidents"), ("user_id", "demo_users")],
        "demo_notifications": [("user_id", "demo_users"), ("ticket_id", "tickets"), ("incident_id", "demo_incidents")],
    }
    for table, fields in references.items():
        for row in tables[table]:
            for field, parent in fields:
                value = row.get(field)
                if value is not None and str(value) not in ids[parent]:
                    raise ValueError(f"Dangling reference: {table}.{field}")
    archived = {str(r["id"]) for r in tables["tickets"] if r.get("deleted_at")}
    archived_incidents = {str(r["id"]) for r in tables["demo_incidents"] if r.get("deleted_at")}
    mapping = {(t, str(r["id"])): uuid4() for t in TABLES for r in tables[t]}
    plan = {}
    for table in TABLES:
        for row in tables[table]:
            key = (table, str(row["id"]))
            target = TARGETS[table]
            if (table == "tickets" and key[1] in archived
                    or table in ("ticket_subtasks", "ticket_events") and str(row["ticket_id"]) in archived
                    or table == "ticket_events" and row["type"] == "DELETED"
                    or table == "demo_incidents" and key[1] in archived_incidents):
                target = None
            plan[key] = target
    digest = hashlib.sha256(json.dumps(tables, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return tables, ids, mapping, plan, digest


def ticket_values(row, events, imported_at):
    history = sorted(events, key=lambda e: e["created_at"])
    questions = [e for e in history if e["type"] in ("QUESTION", "RESOLVED")]
    pending = questions[-1] if questions and questions[-1]["type"] == "QUESTION" else None
    status = "COMPLETED" if row["status"] == "DONE" else row["status"]
    if status == "BLOCKED" and pending:
        status = "BLOCKED_QUESTION"
    if status not in {"TODO", "IN_PROGRESS", "BLOCKED", "BLOCKED_QUESTION", "REDIRECTED", "COMPLETED"}:
        raise ValueError("Unknown ticket status")
    if row["priority"] not in {"LOW", "MEDIUM", "HIGH", "URGENT"}:
        raise ValueError("Unknown ticket priority")
    completed = [e for e in history if e["type"] == "COMPLETED"]
    return dict(title=row["title"], description=row["description"], status=status,
                priority=row["priority"], order_index=row["number"], due_date=dt(row["due_date"]),
                pr_link=row["pr_link"], time_spent_seconds=row["spent_seconds"],
                blocked_time_seconds=row["blocked_seconds"], timer_started_at=None,
                blocked_at=imported_at if status.startswith("BLOCKED") else None,
                blocked_question=pending["text"] if pending and status == "BLOCKED_QUESTION" else None,
                completed_at=dt(completed[-1]["created_at"]) if completed and status == "COMPLETED" else None,
                ticket_type="DEVELOPMENT", estimated_time_seconds=0)


async def run(args):
    from sqlalchemy import insert, select, text
    from sqlalchemy.engine import make_url

    from app.database import dispose_engine, get_session_maker
    from app.models import Application, Epic, Notification, Role, Subtask, Ticket, TicketEvent, User
    from app.models.incident import Incident
    from app.services.auth_service import AuthService

    snapshot = json.loads(await asyncio.to_thread(Path(args.snapshot).read_text, encoding="utf-8-sig"))
    tables, ids, mapping, plan, digest = prepare(snapshot)
    models = {m.__tablename__: m for m in (Application, Epic, Notification, Subtask, Ticket, TicketEvent, User, Incident)}
    imported_at = datetime.now(timezone.utc)
    credentials = []

    def ref(table, value):
        return mapping[(table, str(value))] if value is not None else None

    print("Origen: " + SOURCE_PROJECT)
    print("Filas de origen: " + json.dumps({t: len(tables[t]) for t in TABLES}))
    print("Filas operativas: " + json.dumps(dict(Counter(t for t in plan.values() if t))))
    print(f"Archivo privado íntegro: {sum(len(v) for v in tables.values())} filas")
    validate_destination(make_url(os.environ["DATABASE_URL"]), args.apply)

    try:
        async with get_session_maker()() as db:
            async with db.begin():
                if args.apply:
                    await db.execute(text("SELECT pg_advisory_xact_lock(74813620261006)"))
                    previous = (await db.execute(text(
                        "SELECT digest FROM migration_archive.supabase_batches WHERE source_project=:p"
                    ), {"p": SOURCE_PROJECT})).scalar_one_or_none()
                    if previous:
                        if previous != digest:
                            raise ValueError("Source changed: refuse to overwrite an existing import")
                        print("Importación ya aplicada: sin duplicar ni sobrescribir cambios posteriores.")
                        return
                roles = {r.name: r.id for r in (await db.execute(select(Role))).scalars()}
                if not {"ADMIN", "TEAM_LEADER", "DEVELOPER"}.issubset(roles):
                    raise ValueError("Official roles must exist before importing")
                existing_emails = set((await db.execute(select(User.email))).scalars())
                batch_id = uuid4()
                if args.apply:
                    await db.execute(text(
                        "INSERT INTO migration_archive.supabase_batches "
                        "(id,source_project,digest,exported_at,counts) VALUES "
                        "(:id,:p,:digest,:exported,CAST(:counts AS jsonb))"
                    ), dict(id=batch_id, p=SOURCE_PROJECT, digest=digest,
                            exported=dt(snapshot["exported_at"]), counts=json.dumps({t: len(tables[t]) for t in TABLES})))
                for table in TABLES:
                    for row in tables[table]:
                        source_id = str(row["id"])
                        key = (table, source_id)
                        target = plan[key]
                        values = dict(id=mapping[key], created_at=dt(row.get("created_at")) or imported_at,
                                      updated_at=dt(row.get("created_at")) or imported_at)
                        if target == "users":
                            email = f"supabase-{source_id}@example.com"
                            if email in existing_emails:
                                raise ValueError("Imported email already exists; refusing to overwrite it")
                            role = "TEAM_LEADER" if row["role"] == "GROUP_LEADER" else row["role"]
                            password = secrets.token_urlsafe(24)
                            values.update(email=email, full_name=row["full_name"], role_id=roles[role],
                                          hashed_password=AuthService.hash_password(password),
                                          is_active=bool(args.enable_demo_users and row["is_active"]),
                                          specialty=row.get("specialty"), must_change_password=False,
                                          preferences={"legacy_demo_identity": source_id,
                                                       "avatar_color_hex": row.get("avatar_color_hex")})
                            credentials.append(dict(source_id=source_id, email=email, password=password,
                                                    full_name=row["full_name"], role=role,
                                                    is_active=values["is_active"]))
                        elif target == "applications":
                            values.update(name=row["name"], color=row["color_hex"], is_active=True)
                        elif target == "epics":
                            values.update(title=row["name"], order_index=row["order_index"],
                                          application_id=ref("applications", row["application_id"]), is_collapsed=False)
                        elif target == "tickets":
                            values.update(ticket_values(row, [e for e in tables["ticket_events"] if e["ticket_id"] == row["id"]], imported_at))
                            values.update(epic_id=ref("epics", row["epic_id"]),
                                          assignee_id=ref("demo_users", row["assignee_id"]),
                                          created_by_id=ref("demo_users", row["created_by_id"]))
                        elif target == "subtasks":
                            # Source has no created/completed timestamp; do not invent one for completion.
                            values.update(title=row["title"], is_completed=row["done"], order_index=row["order_index"],
                                          ticket_id=ref("tickets", row["ticket_id"]))
                        elif target == "ticket_events":
                            values.update(ticket_id=ref("tickets", row["ticket_id"]),
                                          user_id=ref("demo_users", row["user_id"]),
                                          to_user_id=ref("demo_users", row["to_user_id"]),
                                          event_type=EVENTS[row["type"]],
                                          detail={"comment": row["text"], "question_text": row["text"],
                                                  "from_status": row["from_status"], "to_status": row["to_status"],
                                                  "source_event_id": source_id,
                                                  "to_user_id": str(ref("demo_users", row["to_user_id"])) if row["to_user_id"] else None})
                        elif target == "incidents":
                            values.update(title=row["title"], description=row["description"],
                                          status=INCIDENT_STATUS[row["status"]], severity=SEVERITY[row["severity"]],
                                          affected_environment="DEV", estimated_resolution_time_seconds=0,
                                          application_id=ref("applications", row["application_id"]),
                                          created_by_id=ref("demo_users", row["reporter_id"]),
                                          assigned_to_id=ref("demo_users", row["assignee_id"]))
                        elif target == "notifications":
                            ticket_key = ("tickets", str(row["ticket_id"]))
                            incident_key = ("demo_incidents", str(row["incident_id"]))
                            values.update(user_id=ref("demo_users", row["user_id"]),
                                          ticket_id=ref(*ticket_key) if plan.get(ticket_key) else None,
                                          incident_id=ref(*incident_key) if plan.get(incident_key) else None,
                                          type=NOTIFICATIONS[row["kind"]], title="Historial de la demo",
                                          message=row["message"], is_read=row["is_read"])
                        if target:
                            statement = insert(models[target]).values(**values)
                            if args.apply:
                                await db.execute(statement)
                            else:
                                statement.compile()
                        if args.apply:
                            await db.execute(text(
                                "INSERT INTO migration_archive.supabase_records "
                                "(source_project,source_table,source_id,batch_id,target_table,target_id,payload) "
                                "VALUES (:p,:t,:s,:b,:target,:id,CAST(:payload AS jsonb))"
                            ), dict(p=SOURCE_PROJECT, t=table, s=source_id, b=batch_id, target=target,
                                    id=mapping[key] if target else None, payload=json.dumps(row, ensure_ascii=False)))
                if args.apply:
                    # Write before commit, so file errors roll back account creation.
                    await asyncio.to_thread(write_credentials, Path(args.credentials), credentials)
            print("Importación confirmada en una transacción." if args.apply else "Dry-run válido; no se escribió ningún registro.")
    finally:
        await dispose_engine()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default=str(BACKEND / ".supabase-import.local.json"))
    parser.add_argument("--env-file", default=str(BACKEND / ".env.vercel.local"))
    parser.add_argument("--credentials", default=str(BACKEND / ".supabase-accounts.local.json"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--enable-demo-users", action="store_true")
    args = parser.parse_args()
    load_dotenv(args.env_file, override=True)
    asyncio.run(run(args))


def validate_destination(url, apply):
    if apply and not (url.host or "").endswith(".neon.tech"):
        raise ValueError("Apply is restricted to the configured Neon database")


def write_credentials(path, credentials):
    # Exclusive creation also avoids a check/write race.
    with path.open("x", encoding="utf-8") as output:
        json.dump({"accounts": credentials}, output, ensure_ascii=False, indent=2)
    path.chmod(0o600)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Importación no completada ({type(exc).__name__}); ninguna credencial se imprime.")
        raise SystemExit(1) from None
