"""Prueba autenticada HTTP -> API -> PostgreSQL de la base cloud nueva.

Solo crea un ticket temporal en una aplicación/épica de verificación;
lo borra al terminar. No imprime contraseñas, tokens ni cookies.
"""
import asyncio
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env.vercel.local", override=True)
load_dotenv(BACKEND / ".env.cloud.admin.local", override=True)


async def main():
    from sqlalchemy import select

    from app.database import dispose_engine, get_session_maker
    from app.models import Ticket

    base = "https://corestream-app-api-grupo1.vercel.app/api"
    async with httpx.AsyncClient(base_url=base, timeout=35) as client:
        health = await client.get("/health")
        assert health.status_code == 200, f"Health HTTP {health.status_code}"
        assert health.json()["checks"] == {"database": "ok", "redis": "ok"}
        print("API HTTPS -> PostgreSQL y Redis: OK (sin bypass de Vercel)")
        login = await client.post("/auth/login", json={
            "email": os.environ["CLOUD_ADMIN_EMAIL"],
            "password": os.environ["CLOUD_ADMIN_PASSWORD"],
        })
        assert login.status_code == 200, f"Login HTTP {login.status_code}"
        client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
        me = await client.get("/auth/me")
        assert me.status_code == 200 and me.json()["role"] == "ADMIN"
        print("Login real + rol ADMIN: OK")
        # Contenedor de pruebas identificado y reutilizado (no datos del wireframe).
        apps = await client.get("/applications/")
        assert apps.status_code == 200, f"Applications HTTP {apps.status_code}; redirect={apps.headers.get('location', '')}"
        app = next((a for a in apps.json() if a["name"] == "Verificación técnica Grupo 1"), None)
        if app is None:
            r = await client.post("/applications/", json={"name": "Verificación técnica Grupo 1", "description": "Contenedor de pruebas de conexión; sin información de clientes."})
            assert r.status_code == 201, f"Application HTTP {r.status_code}"
            app = r.json()
        r = await client.get(f"/epics/by-app/{app['id']}")
        assert r.status_code == 200, f"Epics HTTP {r.status_code}; redirect={r.headers.get('location', '')}"
        epics = [e for e in r.json() if e["application_id"] == app["id"]]
        if epics:
            epic = epics[0]
        else:
            r = await client.post("/epics/", json={"application_id": app["id"], "title": "Validación de persistencia"})
            assert r.status_code == 201, f"Epic HTTP {r.status_code}"
            epic = r.json()
        r = await client.post("/tickets/", json={"epic_id": epic["id"], "title": "Prueba API " + uuid4().hex[:8], "priority": "HIGH", "assignee_id": me.json()["id"]})
        assert r.status_code == 201, f"Create ticket HTTP {r.status_code}"
        ticket_id = r.json()["id"]
        try:
            async with get_session_maker()() as db:
                saved = await db.get(Ticket, UUID(ticket_id))
                assert saved is not None and saved.title == r.json()["title"]
                assert str(saved.assignee_id) == me.json()["id"]
            print("Crear ticket desde HTTPS -> fila de PostgreSQL confirmada: OK")
            changed = await client.put(f"/tickets/{ticket_id}", json={"title": "Prueba persistencia actualizada", "priority": "LOW"})
            assert changed.status_code == 200, f"Update HTTP {changed.status_code}"
            async with get_session_maker()() as db:
                saved = await db.get(Ticket, UUID(ticket_id))
                assert saved.title == "Prueba persistencia actualizada" and saved.priority.value == "LOW"
            print("Actualizar desde HTTPS -> cambios en PostgreSQL confirmados: OK")
            dashboard = await client.get("/mobile/dashboard")
            assert dashboard.status_code == 200, f"Mobile dashboard HTTP {dashboard.status_code}"
            detail = await client.get(f"/mobile/tickets/{ticket_id}/detail")
            assert detail.status_code == 200, f"Mobile detail HTTP {detail.status_code}"
            assert detail.json()["ticket"]["title"] == saved.title
            print("BFF móvil consulta esos mismos datos: OK")
        finally:
            removed = await client.delete(f"/tickets/{ticket_id}")
            assert removed.status_code == 204, f"Delete HTTP {removed.status_code}"
            async with get_session_maker()() as db:
                assert (await db.execute(select(Ticket).where(Ticket.id == UUID(ticket_id)))).scalar_one_or_none() is None
            print("Ticket temporal eliminado en API y PostgreSQL: OK")
        logout = await client.post("/auth/logout", json={})
        assert logout.status_code == 200, f"Logout HTTP {logout.status_code}"
        rejected = await client.get("/auth/me")
        assert rejected.status_code == 401
        print("Logout revoca el JWT en Redis: OK")
    await dispose_engine()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        message = str(exc) if isinstance(exc, AssertionError) else type(exc).__name__
        print("Verificación incompleta: " + message)
        raise SystemExit(1) from None
