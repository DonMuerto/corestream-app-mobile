# mobile_api — Endpoints de backend para CoreStream Mobile

## Integración con el fork actual (Grupo 1, 2026-10-05)

La entrega original de agosto se conserva como referencia; sus instrucciones
de instalación de abajo no deben aplicarse literalmente al fork actual.
La integración activa añade `/api/mobile/*` y `/api/devices/*`. Usa usuarios
de PostgreSQL, `TEAM_LEADER`, `COMPLETED`, `BLOCKED_QUESTION` y el detalle
JSONB de los eventos. Alembic encadena `mobile_0001` desde `i5j6k7l8m9n0`;
no se usa `create_all()` al arrancar.

No se registran los adaptadores antiguos `auth_ext`, `websocket_mobile` ni
`ticket_assign`: se conservan el logout con revocación de JTI, WebSocket con
ticket opaco de un solo uso y la actualización canónica de asignaciones.
Nunca enviar el JWT en la URL de un socket.

Las pruebas de aceptación actuales, con login real, están en
`tests/integration/test_mobile_base.py`. `mobile_api/tests/test_api.py` es
material de referencia del backend anterior, no la suite del fork actual.
FCM aún no está configurado. La cola ARQ conserva el diseño oficial de Docker
y requiere adaptar su ejecución a Vercel; no se considera operativa solo por
disponer de Redis. El BFF y las tablas de dispositivos/preferencias sí lo son.

---

Implementación de la **"Especificación de API — CoreStream Mobile v1.0"**
(`CoreStream-Mobile-Especificacion-API.docx`) como paquete autocontenido:
**no modifica ningún archivo existente** del backend. Los únicos cambios a
código existente están documentados en `patches/CAMBIOS_EN_CODIGO_EXISTENTE.md`
para aplicarlos cuando el equipo decida.

## Contenido

| Ruta | Especificación | Qué hace |
|---|---|---|
| `routers/devices.py` | §4.1–4.5 | Registro de tokens FCM, baja de dispositivos, preferencias push |
| `routers/auth_ext.py` | §4.6 | `POST /auth/logout` con revocación de refresh token en Redis |
| `routers/mobile.py` | §5.1–5.4 | BFF móvil: dashboard por rol, tablero de proyecto, detalle de ticket con `permissions`, carga del equipo |
| `routers/ticket_assign.py` | §6.1 | `POST /tickets/{id}/assign` con evento + notificación |
| `routers/websocket_mobile.py` | §7.1 | `WS /ws/mobile/notifications?token=` autenticado por JWT |
| `models/device.py` | §9.1 | `user_devices`, `notification_preferences` |
| `services/push_service.py` | §9.2 | FCM (firebase-admin) con **modo simulado** sin credenciales |
| `services/permission_service.py` | §5.3 | Cálculo puro del bloque `permissions` |
| `services/token_blacklist.py` | §4.6 | Lista de refresh tokens revocados (Redis, TTL automático) |
| `migrations/2026_08_27_0001_mobile_devices.py` | §9.1, §7.2 | Migración Alembic |
| `tests/` | — | pytest: permisos (sin BD) + integración (con PostgreSQL) |

## Instalación (5 pasos)

1. **Copiar** esta carpeta a `corestream/backend/mobile_api/` (junto a `app/`).

2. **Dependencias** (firebase-admin es opcional en desarrollo):

   ```bash
   pip install -r mobile_api/requirements-mobile.txt
   ```

3. **Registrar los routers** — único cambio en `app/main.py` (2 líneas):

   ```python
   import mobile_api.models          # registra las tablas nuevas en Base
   from mobile_api import include_mobile_routers
   include_mobile_routers(app)
   ```

   En desarrollo, `Base.metadata.create_all` del startup crea las tablas nuevas.

4. **Migración** (producción): copiar `migrations/2026_08_27_0001_mobile_devices.py`
   a `alembic/versions/`, ajustar `down_revision` a la head actual
   (`alembic heads`) y ejecutar `alembic upgrade head`. Además de las tablas,
   añade `notifications.incident_id` y los valores `INCIDENT_*` al enum (§7.2).

5. **Parches al código existente** (`patches/CAMBIOS_EN_CODIGO_EXISTENTE.md`):
   el nº 2 (verificar revocación en `/auth/refresh`) es necesario para que el
   logout sea efectivo; el resto son recomendados/opcionales. Todo funciona
   sin ellos con degradación documentada.

## Configuración

| Variable | Efecto |
|---|---|
| `FIREBASE_CREDENTIALS_JSON` | Ruta al JSON de cuenta de servicio de Firebase, o el JSON inline. **Sin definir: modo simulado** — los push se registran en el log `mobile_api.push` y nada falla. |

## Estado de verificación

La suite completa (19 tests: 8 de permisos + 11 de integración) se ejecutó en
verde contra el código real de `app/` y PostgreSQL 16. Para que el backend
existente arranque sobre una base de datos limpia es necesario aplicar antes
las correcciones del punto 0 de `patches/CAMBIOS_EN_CODIGO_EXISTENTE.md`
(bugs preexistentes del repo: un import inválido en `app/models/base.py`,
índices duplicados en los modelos y los imports `app.core.*` del módulo de
incidencias).

## Probar

```bash
# Tests puros (sin base de datos):
pytest mobile_api/tests/test_permissions.py -v

# Tests de integración (crean y limpian sus propios datos):
export TEST_DATABASE_URL=postgresql+asyncpg://corestream:corestream@localhost:5432/corestream_test
pytest mobile_api/tests -v
```

Prueba manual rápida con la API levantada (Swagger: `/api/docs`):

```bash
TOKEN=$(curl -s -X POST localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"...","password":"..."}' | jq -r .access_token)

curl -s localhost:8000/mobile/dashboard -H "Authorization: Bearer $TOKEN" | jq
curl -s -X POST localhost:8000/devices/ -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"fcm_token":"token-de-prueba","platform":"ANDROID"}' | jq
```

## Decisiones de implementación

- **BFF de solo lectura**: los endpoints `/mobile/*` no introducen reglas de
  negocio; agregan datos de los modelos existentes. Las acciones siguen
  pasando por los endpoints canónicos (start/complete/question/redirect).
- **`permissions` en servidor**: la app pinta botones según ese bloque, pero
  cada acción se re-valida en su endpoint; un cliente manipulado no consigue
  nada.
- **Tipos de incidencia en notificaciones**: hasta aplicar el parche §7.2,
  `INCIDENT_REPORTED/INCIDENT_ASSIGNED` se persisten como `SYSTEM` (el push y
  el payload WebSocket conservan el tipo real para el deep link).
- **Columna de datos de eventos**: el nombre difiere entre versiones del
  modelo `TicketEvent` (`payload`/`data`/`event_metadata`); el código detecta
  la que exista.
- **Volúmenes**: las agregaciones del BFF se calculan en memoria; con los
  volúmenes de CoreStream (decenas de tickets por app) es más simple y
  suficientemente rápido. Si crece, sustituir por consultas `GROUP BY`.
