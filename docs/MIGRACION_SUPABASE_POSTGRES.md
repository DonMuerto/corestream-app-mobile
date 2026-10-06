# Traslado de la demo a PostgreSQL — 2026-10-06

Cliente móvil Flutter: https://corestream-app-base-grupo1.vercel.app/.
FastAPI: https://corestream-app-api-grupo1.vercel.app/api.
Repositorio `DonMuerto/corestream-app-mobile`, rama única `desarrollo`.
La demo antigua y `main` no se reemplazaron.

## Qué base se utiliza

Neon es PostgreSQL real alojado en la nube. Supabase también utilizaba
PostgreSQL, pero su esquema de demostración no era el esquema del backend
oficial. Se adaptaron las relaciones mediante UUID v4, sin cambiar el contrato
de las tablas operativas oficiales ni copiar las políticas anónimas de Supabase.

La app publicada usa Vercel (Flutter Web/FastAPI), Neon (PostgreSQL) y Upstash
(Redis TLS). No consulta PostgreSQL del PC. Docker puede detenerse sin afectar
esa URL. Docker mantiene el entorno local: PostgreSQL 15, Redis 7, API, worker
ARQ y web Vue de referencia; `localhost` sí depende de estos servicios.
Cerrar solo la ventana de Docker Desktop puede dejar el motor activo.
`scripts/local.ps1 Stop` detiene únicamente el stack local y conserva sus
volúmenes. No se detuvo Docker automáticamente.

## Datos trasladados

| Entidad de origen | Filas originales | Tabla operativa de destino |
| --- | ---: | --- |
| Usuarios de demostración | 5 | `users`: 5 perfiles importados |
| Aplicaciones | 3 | `applications`: 3 |
| Épicas | 5 | `epics`: 5 |
| Tickets | 15 | `tickets`: 12 activos; 3 archivados solo en el archivo privado |
| Subtareas | 20 | `subtasks`: 20 |
| Eventos de tickets | 39 | `ticket_events`: 26 de tickets activos; 13 en el archivo |
| Incidencias | 5 | `incidents`: 5 |
| Comentarios de incidencias | 1 | Archivo privado: no existe equivalente en el esquema oficial |
| Notificaciones | 25 | `notifications`: 25 |

Las **118 filas originales completas** se conservaron también en
`migration_archive.supabase_records`, con mapeo hacia el UUID de destino.
Los tickets T-148, T-149 y T-150 permanecen archivados, no reaparecen en el
tablero. Se preservaron los títulos, descripciones, relaciones, responsables,
segundos de trabajo/bloqueo, enlaces PR, fechas originales e historial.

Los números antiguos, códigos, categorías y otros campos sin equivalente
operativo siguen disponibles en `payload`; no se inventaron columnas oficiales
ni se descartaron esos datos. El comentario de incidencia está conservado,
pero aún no hay pantalla/API oficial para mostrarlo.

Se pausaron los cronómetros al importar, conservando exactamente los segundos
guardados. Los relojes antiguos completos están en el archivo; no se sumaron
las semanas de inactividad como trabajo. Los bloqueos conservan su estado y
reanician su medición desde el traslado, sin sumar la pausa del proyecto.

`GROUP_LEADER` pasa a `TEAM_LEADER`; `DONE` a `COMPLETED`; una pregunta pendiente
bloqueada pasa a `BLOCKED_QUESTION`. Incidencias: `OPEN` → `REPORTED`,
`IN_PROGRESS`/`UNDER_REVIEW` → `INVESTIGATING`, `RESOLVED` se conserva;
`CRITICAL` → `P1`, `HIGH` → `P2`, `MEDIUM`/`LOW` → `P3`. El valor original
completo se conserva siempre en el archivo. El entorno de estas incidencias
de demostración se identifica como `DEV`.

El administrador cloud anterior, la aplicación y la épica de verificación se
preservaron. Los totales actuales pueden incluir tickets nuevos de pruebas.
Supabase se reactivó para leer el origen; no se borró ni modificó su contenido.
Las escrituras de la app nueva no se sincronizan de vuelta con la demo antigua.

## Usuarios y login

Los cinco perfiles originales eran ficticios y no tenían correo ni contraseña.
Con autorización se habilitaron cuentas de prueba independientes, con correos
`supabase-u1@example.com` … `supabase-u5@example.com` y contraseñas aleatorias
individuales. No son correos de personas reales ni destinatarios de envío.

Las credenciales están **solo localmente** en
`backend/.supabase-accounts.local.json`. Tanto este archivo como el snapshot
se excluyen de Git y de la subida a Vercel. Los hashes usan la implementación
oficial SHA-256 + bcrypt; no hay contraseña compartida ni selector sin login.
Las altas normales siguen siendo por invitación, sin registro público.

## Revisar los datos en Neon

Desde Vercel → Storage → `corestream-app-postgres-grupo1` → abrir Neon →
Tables/Data o SQL Editor. Seleccionar la base/branch conectada a la API, no
la base `corestream` de Docker. Consultas de solo lectura:

```sql
SELECT u.full_name, u.email, r.name AS role, u.is_active
FROM public.users u JOIN public.roles r ON r.id = u.role_id
ORDER BY u.full_name;

SELECT t.id, t.title, t.status, t.priority, u.full_name AS responsible,
       t.time_spent_seconds, t.blocked_time_seconds, t.pr_link
FROM public.tickets t LEFT JOIN public.users u ON u.id = t.assignee_id
ORDER BY t.created_at DESC;

SELECT source_table, count(*) AS preserved_rows
FROM migration_archive.supabase_records GROUP BY source_table;

SELECT payload->>'number' AS old_number, payload->>'title' AS title,
       payload->>'deleted_at' AS archived_at
FROM migration_archive.supabase_records
WHERE source_table = 'tickets' AND payload->>'deleted_at' IS NOT NULL;

SELECT e.event_type, e.created_at, u.full_name, e.detail
FROM public.ticket_events e LEFT JOIN public.users u ON u.id = e.user_id
WHERE e.ticket_id = '<UUID_DEL_TICKET>' ORDER BY e.created_at;
```

El archivo privado no tiene rutas públicas en FastAPI ni permisos `PUBLIC`.
No confundirlo con una auditoría inmutable: sigue pendiente ese requisito.
El endpoint oficial DELETE de tickets elimina físicamente y en cascada; esta
migración no cambia esa semántica. No utilizarlo para limpiar datos importados.

## Repetibilidad y pruebas

Alembic `supabase_import_0001` añade solamente el esquema privado.
`scripts/import_supabase_demo.py` hace dry-run por defecto, exige el proyecto
de origen esperado y las nueve tablas, valida referencias y usa una transacción
única para la carga. `--apply` restringe el destino a Neon. Repetir el mismo
snapshot no duplica ni sobrescribe datos; un snapshot cambiado se rechaza.

`scripts/verify_supabase_import.py` compara cada payload archivado con el
snapshot y verifica filas operativas, relaciones, tiempos y login/dashboard
de las cinco cuentas por el mismo HTTPS que usa Flutter.

```powershell
cd backend
python scripts/import_supabase_demo.py
python scripts/verify_supabase_import.py
python scripts/verify_supabase_import.py --ui-title "Prueba Flutter UI migración PostgreSQL 2026-10-06"
```

Requiere las dependencias del backend y los archivos privados locales.
No ejecutar la suite de integración contra Neon: usa `corestream_test` y
Redis 15, nunca datos del proyecto.

Verificado: ocho tests nuevos de mapeo/migración e idempotencia pasaron en
PostgreSQL local; reconciliación de las 118 filas en Neon; login y dashboard
de cinco roles por HTTPS; creación de ticket desde Flutter y confirmación SQL;
asignación a Diego desde la web. Los tests de Flutter en Windows siguen sujetos
al bloqueo de Control de aplicaciones ya documentado; no se deshabilitó.

Esto es una base persistente más cercana a un MVP, no una certificación de
producto completo. Los datos importados siguen siendo de demostración. FCM,
consumidor ARQ cloud, sesión móvil persistente, invitaciones en UI, MFA/SSO,
multi-tenancy y auditoría/retención siguen pendientes según las guías del grupo.
