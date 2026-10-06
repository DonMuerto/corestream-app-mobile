# Cambios a aplicar en el código existente

El paquete `mobile_api/` no modifica ningún archivo del proyecto. Estos
cambios sí tocan código existente y quedan documentados aquí para que el
equipo los aplique cuando decida (todos son pequeños y retrocompatibles).

---

## 0. Correcciones previas al backend existente (bugs encontrados al verificar)

Al ejecutar la suite de integración de `mobile_api/tests` contra el código
actual del repositorio y una base de datos PostgreSQL limpia aparecieron
estos defectos **preexistentes** (no los introduce el módulo móvil; el 0.1 y
el 0.3 impiden incluso arrancar/importar partes del backend):

**0.1 — `app/models/base.py` (línea 11): import inválido.** El módulo no importa:

```python
from typing import UUID as PyUUID    # ✗ typing no tiene UUID
# debe ser:
from uuid import UUID as PyUUID      # ✓
```

**0.2 — Índices duplicados en todos los modelos.** Las columnas declaran
`index=True` y además `__table_args__` repite `Index("ix_<tabla>_<col>", ...)`
con el mismo nombre. En una BD limpia, `Base.metadata.create_all` (startup) y
las migraciones fallan con `DuplicateTableError: relation "ix_users_email"
already exists`. Solución: eliminar los `Index(...)` duplicados de
`__table_args__` (o quitar los `index=True`), en `user.py`, `ticket.py`,
`epic.py`, `application.py`, `subtask.py`, `ticket_event.py`,
`notification.py`, `document.py` e `incident.py`.

**0.3 — El módulo de incidencias importa una ruta inexistente.**
`app/models/incident.py`, `app/routers/incidents.py` y
`app/services/notification_service.py` hacen `from app.core.database import ...`,
pero el paquete `app.core` no existe en este repo (el módulo se escribió para
otra estructura). Cambiar a `from app.database import ...`. Además, exportar
`Incident` en `app/models/__init__.py`. Mientras esto no se corrija,
`mobile_api` lo detecta y el dashboard/carga de equipo omiten incidencias
(con warning en el log).

**0.4 — FKs `SET NULL` sobre columnas NOT NULL.** `ticket_events.user_id` y
`notifications.user_id` son `nullable=False` pero sus FKs a `users` declaran
`ondelete="SET NULL"`: eliminar un usuario con eventos o notificaciones lanza
`NotNullViolationError`. Decidir por columna: o `nullable=True` (conservar el
histórico sin autor) o `ondelete="CASCADE"`.

---

## 1. Registrar los routers móviles — `app/main.py` (obligatorio)

Junto al resto de `include_router`:

```python
from mobile_api import include_mobile_routers

include_mobile_routers(app)
```

Y para que `Base.metadata.create_all` del startup cree las tablas nuevas
en desarrollo, importar los modelos antes del `create_all`:

```python
import mobile_api.models  # noqa: F401  (registra user_devices y notification_preferences)
```

En producción usar la migración `mobile_api/migrations/2026_08_27_0001_mobile_devices.py`
(copiarla a `alembic/versions/` y ajustar `down_revision`).

---

## 2. §4.6 — Verificar revocación en `POST /auth/refresh` — `app/routers/auth.py` (obligatorio para que el logout sea efectivo)

Al inicio de `refresh_token(...)`, antes de emitir tokens nuevos:

```python
from mobile_api.services.token_blacklist import is_refresh_token_revoked

if await is_refresh_token_revoked(payload.refresh_token):
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token inválido o ya revocado",
    )
```

*(adaptar `payload.refresh_token` al nombre real del campo en ese endpoint).*

---

## 3. §7.2 — `incident_id` y tipos de incidencia en notificaciones (recomendado)

### 3a. `app/models/notification.py`

Añadir a la clase `NotificationType`:

```python
    INCIDENT_REPORTED = "INCIDENT_REPORTED"
    INCIDENT_ASSIGNED = "INCIDENT_ASSIGNED"
```

Añadir a la clase `Notification` (junto a `ticket_id`):

```python
    incident_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Referencia a la incidencia relacionada con esta notificación",
    )
```

### 3b. `app/schemas/notification.py`

En `NotificationResponse`, añadir el campo y los tipos válidos:

```python
    incident_id: Optional[UUID] = None
```

y en `valid_types` del validador: `"INCIDENT_REPORTED", "INCIDENT_ASSIGNED"`.

La columna y los valores del enum en PostgreSQL los crea la migración
`mobile_0001`. Mientras este parche no esté aplicado, `PushService.notify_user`
persiste esos tipos como `SYSTEM` (el push conserva el tipo real), así que
nada se rompe si se aplica después.

### 3c. Emitir la notificación al crear incidencias — `app/routers/incidents.py`

En `create_incident(...)`, tras crear la incidencia, notificar a líderes:

```python
from mobile_api.services.push_service import PushService
from sqlalchemy import select

leads = (await db.execute(
    select(User).where(User.role.in_(["ADMIN", "GROUP_LEADER"]), User.is_active == True)
)).scalars().all()
for lead in leads:
    if str(lead.id) == str(current_user.sub):
        continue
    await PushService.notify_user(
        db, str(lead.id),
        title="Nueva incidencia",
        message=f"{reporter_name} reportó una incidencia en {app_name}: “{incident.title}”",
        notification_type="INCIDENT_REPORTED",
        incident_id=str(incident.id),
    )
```

*(y lo análogo con `INCIDENT_ASSIGNED` en `assign_incident`).*

---

## 4. §7.3 — Registro de dispositivo en el login — `app/routers/auth.py` (opcional)

En el esquema de entrada del login, añadir el campo opcional:

```python
from mobile_api.schemas.auth_ext import LoginDevice

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    device: Optional[LoginDevice] = None   # <- nuevo
```

Y en `login(...)`, tras autenticar con éxito (un fallo aquí NO revierte el login):

```python
if credentials.device:
    try:
        from sqlalchemy import select
        from mobile_api.models.device import UserDevice

        result = await db.execute(
            select(UserDevice).where(UserDevice.fcm_token == credentials.device.fcm_token)
        )
        device = result.scalar_one_or_none()
        if device is None:
            device = UserDevice(fcm_token=credentials.device.fcm_token)
            db.add(device)
        device.user_id = user.id
        device.platform = credentials.device.platform.value
        device.device_name = credentials.device.device_name
        device.app_version = credentials.device.app_version
        device.is_active = True
        await db.commit()
    except Exception:
        pass  # la app reintentará con POST /devices/
```

---

## 5. §7.1 — Deprecar el WebSocket antiguo (recomendado)

`/ws/notifications/{user_id}` (en `app/routers/websocket.py`) identifica al
usuario sin verificar el token. El endpoint nuevo `/ws/mobile/notifications?token=`
lo sustituye para móvil y también sirve para la web. Plan sugerido: migrar el
frontend web al endpoint nuevo y eliminar el antiguo; como mínimo, no
exponerlo fuera de la red interna.
