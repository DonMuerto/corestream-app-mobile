# Ver PostgreSQL y comprender el login

## Acceso a los datos

La app `corestream-app-base-grupo1.vercel.app` consume FastAPI, que guarda
datos en PostgreSQL de Neon (`corestream-app-postgres-grupo1`). Redis TLS
en Upstash gestiona revocaciones, tickets WebSocket y cola/pub-sub.
Supabase de la demo antigua y PostgreSQL de Docker son bases independientes;
sus filas no se importan automáticamente a Neon.

[Abrir el recurso en Vercel](https://vercel.com/d/dashboard/integrations/neon/icfg_sFovqOaYaDz9p5RpeIyCdyOA/resources/store_43QgZDkl14q4Dd5q).
En `Browser`, usar `Data Editor` para filas, `Query` para SQL y `Schema` para
relaciones. Alternativa: `Open in Neon` y su editor de tablas/SQL.
Se necesita la cuenta propietaria, no las credenciales de login de Flutter.
[Referencia oficial](https://vercel.com/changelog/query-and-manage-marketplace-databases-from-the-dashboard).

## Consultas de lectura

Usuarios y roles, sin contraseña/hash:

```sql
SELECT u.id, u.email, u.full_name, r.name AS role, u.is_active, u.created_at
FROM users u JOIN roles r ON r.id = u.role_id
ORDER BY u.created_at DESC;
```

Invitaciones, sin exponer token/hash:

```sql
SELECT email, role, created_at, expires_at, used_at
FROM invitations ORDER BY created_at DESC;
```

Tickets, responsable y tiempos:

```sql
SELECT t.id, t.title, t.status, t.priority, u.full_name AS responsable,
       t.time_spent_seconds, t.blocked_time_seconds,
       t.timer_started_at, t.updated_at
FROM tickets t LEFT JOIN users u ON u.id = t.assignee_id
ORDER BY t.updated_at DESC;
```

Historial operativo:

```sql
SELECT e.ticket_id, e.event_type, u.full_name AS actor, e.detail, e.created_at
FROM ticket_events e LEFT JOIN users u ON u.id = e.user_id
ORDER BY e.created_at DESC LIMIT 50;
```

Volver a ejecutar la consulta/refrescar el editor después de actuar desde
Flutter. No esperar una escritura por segundo del contador visual: los tiempos
se acumulan al pausar/sincronizar/cambiar estado. No editar roles, contraseñas
ni estados directamente para simular flujos: deben pasar por la API.

En el backend oficial, eliminar un ticket es un borrado físico con cascadas,
no el archivado lógico de la demo Supabase. `ticket_events` tampoco sustituye
la auditoría inmutable externa de TRV-07.

## Login no significa registro

No existe `POST /auth/register`. El administrador invita por correo y rol;
el destinatario acepta el enlace, elige nombre/contraseña, y entonces se crea
la fila en `users` y se marca `invitations.used_at`. Enlaces de un uso, siete días.

1. `POST /api/invitations/`: ADMIN invita cualquier rol; TEAM_LEADER solo
   DEVELOPER. Guarda una invitación, no una cuenta utilizable todavía.
2. `GET /api/invitations/{token}`: consultar invitación sin iniciar sesión.
3. `POST /api/invitations/{token}/accept`: crear la cuenta del invitado.
4. `POST /api/auth/login`: validar una cuenta existente.

Existe además `POST /api/users/`, alta administrativa protegida, no registro
público. Para el flujo solicitado debe usarse invitación, no un formulario abierto.

Flutter tiene login, pero todavía no gestión/aceptación de invitaciones ni
deep link correspondiente. SMTP no está configurado. Un enlace generado por
API se compartiría a mano hasta desarrollar UI/configurar correo; no presentar
ese flujo móvil como terminado. No publicar enlaces/tokens de invitación.

## Estado comprobado el 2026-10-06

Consulta directa de Neon en transacción de solo lectura:

- Migración `mobile_0001`.
- Un usuario: `admin.grupo1@corestream.dev`, ADMIN, activo.
- Cero invitaciones y dispositivos.
- Una aplicación/épica de verificación; cero tickets.

La contraseña generada está solo en `backend/.env.cloud.admin.local` del PC,
ignorada por Git y despliegues. No hay contraseña pública por defecto ni cuentas
del grupo precargadas. Clonar código/aplicar migraciones no importa usuarios.

Login no crea otro usuario: valida la cuenta y emite tokens. Las revocaciones
se guardan en Redis, no como filas nuevas de usuarios en PostgreSQL.
Login desde Flutter y persistencia de un ticket de su tablero fueron verificados
en la base alojada; se limpiaron los tickets temporales después de comprobarlos.
