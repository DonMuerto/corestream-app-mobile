# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Convenciones de colaboración

- Commits: nunca agregar línea de coautoría (ni `Co-Authored-By`). Mensajes cortos y precisos, lo mínimo necesario para entenderse.
- Comentarios en código: siempre en inglés, lo mínimo necesario.

## Qué es esto

CoreStream: plataforma de gestión de proyectos/tickets (Kanban) para equipos de desarrollo. Backend FastAPI (Python 3.11, async de punta a punta) + Vue 3/TS/Vite en el frontend, PostgreSQL 15 y Redis 7, con un worker ARQ separado para notificaciones/tareas en segundo plano y WebSockets sobre pub/sub de Redis.

## Comandos

Todo corre en Docker; Node/Python locales solo hacen falta para autocompletado del editor.

```bash
# Levantar entorno de desarrollo (bind mounts, hot-reload, Postgres/Redis propios y descartables)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

# Salud del stack
docker compose ps                        # 5 servicios deben estar "healthy"
curl http://localhost:8000/api/health    # {"status":"ok", "checks": {...}}

# Tests backend
docker compose exec backend pytest tests/ --ignore=tests/integration -q   # unitarios, SQLite en memoria
docker compose exec backend pytest tests/integration -q                    # requieren Postgres/Redis reales
docker compose exec backend pytest tests/test_tickets.py::test_name -q     # un test puntual

# Lint / types backend
docker compose exec backend ruff check app/ tests/
docker compose exec backend mypy app/

# Primer admin (no hay seeder ni usuario por defecto; el resto se crea por invitación)
docker compose exec backend python -m app.scripts.create_admin --email x@y.com --password "..."
```

Frontend (`frontend/`), fuera de Docker si hace falta iterar rápido con tipos:

```bash
npm run dev          # servidor Vite (usado dentro del overlay de dev)
npm run type-check   # vue-tsc --noEmit
npm run test:unit    # vitest
npm run test:e2e     # cypress run
npm run build
```

URLs en desarrollo: frontend `http://localhost:5173`, backend `http://localhost:8000`, Swagger en `http://localhost:8000/api/docs` (deshabilitado si `ENVIRONMENT=production`).

## Los dos perfiles de Docker Compose

No es un fichero con condicionales, son dos que se combinan:

- `docker-compose.yml` — perfil de **producción**, el que corre en la VM. Imágenes construidas, sin bind mounts ni `--reload`. **No levanta Postgres ni Redis propios**: se conecta a instancias ya existentes en la VM (`db-postgre`, `directa-redis-1`), compartidas con otros proyectos, con su propia base/usuario dentro de esas instancias.
- `docker-compose.dev.yml` — overlay de **desarrollo**: bind mounts, servidor de Vite, y Postgres/Redis propios y descartables.

Para desarrollo local siempre se usan los dos juntos (ver comando arriba). Para probar el perfil de producción tal cual se despliega, ver `docs/DEPLOYMENT.md` y `docs/SETUP.md`.

Detalle de despliegue en la VM: puertos publicados en `0.0.0.0` sin Nginx local (enrutamiento público externo a la máquina); backend en `8010`, frontend en `8080` (8000 lo usa otro proyecto de la VM). El aislamiento de Redis frente a otros proyectos es solo por prefijo de claves/canales (`corestream:`), no por número de base de datos.

## Arquitectura backend (`backend/app/`)

- `routers/` — un módulo por dominio (`auth`, `tickets`, `epics`, `applications`, `subtasks`, `documents`, `uploads`, `notifications`, `invitations`, `teams`, `meetings`, `incidents`, `support_tickets`, `analytics`, `websocket`, `ticket_redirection`).
- `services/` — lógica de negocio: `ticket_state_machine.py`, `ticket_permissions.py`, `ticket_redirection.py`, `notification_service.py`, `translation_service.py`, `timer_service.py`, `transition_audit.py`, `auth_service.py`, `email_service.py`, `file_service.py`, `analytics_service.py`.
- `models/base.py` — **toda `relationship()` debe declarar `lazy="raise_on_sql"`** (no `"raise"` a secas, no el `"select"` por defecto). La app usa `AsyncSession` exclusivamente, que no soporta lazy loading implícito; sin esto, una relación no precargada revienta en producción con `MissingGreenlet` al serializar con Pydantic. `raise_on_sql` falla ruidosamente en desarrollo/CI en el momento en que de verdad haría falta una consulta, pero no rompe accesos que se resuelven sin tocar la base (ej. FK a NULL en un `if self.relacion else None`).
- Esquema de BD gestionado únicamente por Alembic; `alembic upgrade head` corre al arrancar el contenedor y **si la migración falla, el contenedor no arranca** (sin arranque silencioso contra un esquema a medio migrar).
- El worker ARQ corre en un contenedor separado (`command: python -m arq app.worker.settings.WorkerSettings`) sobre una cola propia (`corestream:arq:queue`, no el nombre por defecto de la librería) — el `default_queue_name` del pool en `main.py` debe coincidir con `queue_name` en `worker/settings.py`.

### RBAC (referencia autoritativa en `docs/RBAC.md` — actualizar en el mismo commit que cualquier cambio de autorización)

Roles: `ADMIN` (administra usuarios/estructura, no ejecuta trabajo operativo sobre tickets), `TEAM_LEADER` (gestiona el trabajo de su equipo + todo lo de DEVELOPER sobre tickets propios), `DEVELOPER` (solo actúa sobre tickets/subtareas/documentos propios). El mecanismo en uso es `require_role(...)` de `middleware/auth.py` (el decorador `require_permissions`/`RBACRole` de `middleware/rbac.py` es histórico, sin llamadas activas). Un rol desconocido lanza `ValueError`/`RuntimeError`, nunca deniega en silencio.

Helpers de ownership en `app/services/ticket_permissions.py` (usados por `routers/tickets.py`, `subtasks.py`, `documents.py`): `require_non_admin`, `require_admin_or_leader`, `assert_can_manage_ticket`, `assert_is_current_assignee`, `claim_or_assert_assignee`, `is_admin_or_leader`.

### Tiempo real (Redis pub/sub)

Todos los canales/claves llevan prefijo `corestream:`. Flujo: cambio de estado de ticket → guardado en Postgres → evento publicado (`corestream:tickets:updates` o `corestream:user:{id}:notifications`) → worker ARQ lo procesa → WebSocket lo entrega. El endpoint WS usa dos tareas de larga vida coordinadas con `asyncio.wait(..., return_when=FIRST_COMPLETED)` (evitar volver al patrón de recrear tareas en cada iteración de un loop sin timeout real — saturaba CPU con conexiones inactivas).

Autenticación WS: ticket de un solo uso de 15s (`POST /api/auth/ws-ticket`), no el JWT en el query string (evita que quede en logs de acceso de un proxy).

### Seguridad

JWT access (corta duración) + refresh (httpOnly, `SameSite=Strict`, solo viaja a `/api/auth/refresh`), claim `type` y `jti` para revocación individual en logout. CSRF por doble envío (cookie `csrf_token` + header `X-CSRF-Token`) en toda mutación que dependa de la cookie de refresh. Contraseñas: bcrypt con pre-hash SHA-256 (evita el límite de 72 bytes de bcrypt sin truncar la contraseña real). Alta de usuarios exclusivamente por invitación, sin registro público.

## Tests backend

- `tests/` (raíz) — unitarios, lógica pura, SQLite en memoria, rápidos.
- `tests/integration/` — requieren Postgres y Redis reales, marcados con `integration`; crean/migran su propia base (`corestream_test`) por sesión, no tocan datos de desarrollo.
- `pytest.ini`: `asyncio_mode = auto`, loop de eventos de ámbito de sesión (los tests de integración comparten un único cliente HTTP/loop en vez de levantar el lifespan completo en cada test).

## Lint (ruff)

Set de reglas deliberadamente acotado (`F`, `E4`, `E7`, `E9`, `I`, `ASYNC`, `B`, `PLE`, `RUF100`) — no el default de ruff, que hoy generaría ~776 avisos de modernización sin ganancia real. `B008` ignorado a propósito (patrón `Depends(...)` de FastAPI en defaults). `B904` ignorado temporalmente (falta `from exc` en `raise HTTPException` dentro de varios `except`; pendiente de una fase de observabilidad). Violaciones `ASYNC230`/`ASYNC240` conocidas están marcadas una a una con `# noqa` explicado, no silenciadas globalmente, para que cualquier violación *nueva* siga rompiendo CI.

## Dependencias

Versiones fijadas en `requirements.txt` a propósito (antes iban sin pin y una reconstrucción de imagen podía traer un mayor incompatible sin avisar). Para actualizar: cambiar el pin, reconstruir la imagen, correr la suite completa de tests, y solo entonces commitear.

## Backups (producción)

`backend/scripts/backup_db.sh` / `restore_db.sh` — dump de la base `corestream` + tar del volumen de storage. Ver `docs/DEPLOYMENT.md` para el cron sugerido en la VM.
