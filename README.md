# CoreStream App — Grupo 1

Repositorio: https://github.com/DonMuerto/corestream-app-mobile.
Solo se desarrolla en `desarrollo`; `main` y `mejoras/pantalla-login` se
conservan sin cambios. La demo antigua sigue recuperable en el historial.

## Base de desarrollo

- `mobile/`: cliente Flutter del grupo, con plataformas Android/Web.
- `backend/`: FastAPI compartido, SQLAlchemy async, Alembic, PostgreSQL,
  Redis y adaptación de los endpoints `mobile_api` entregados en Drive.
- `frontend/`: web Vue original conservada como referencia y para Docker,
  no el entregable móvil ni el cliente publicado en el nuevo proyecto Vercel.
- `docs/`: puesta en marcha, consulta de datos y requisitos pendientes.

Se conserva el historial oficial hasta
`94cb390d3b7b35ca6f0aa826f1512a501e7fddf3` del fork
`josenavarrete666/Corestream_Grupo1` como segundo padre del commit de traslado.
El código se publica con autorización, sin secretos ni datos de usuarios.

## Acceso

- Flutter: https://corestream-app-base-grupo1.vercel.app/
- API: https://corestream-app-api-grupo1.vercel.app/api
- PostgreSQL en Neon; Redis TLS en Upstash. No usa la demo Supabase.
- Login real, sin registro público ni cuentas mock activas por defecto.
  Primer administrador preparado manualmente; demás usuarios por invitación.
  Se migraron los cinco perfiles persistidos de la demo como cuentas de prueba
  autenticadas; no hay datos mock en memoria en la app publicada. Ver la guía
  de traslado para sus credenciales privadas y las equivalencias del esquema.

Esta base no completa aún todos los requisitos del Grupo 1: faltan las
pantallas de invitaciones, refresh/almacenamiento seguro móvil, FCM,
multi-tenancy, feature gating, auditoría, MFA/SSO y biometría.

## Empezar

```powershell
.\scripts\local.ps1 Start
cd mobile
flutter pub get
flutter run -d chrome --web-port 7357 --dart-define=CS_API_URL=http://localhost:8000/api
```

Android con API alojada, desde `mobile/`:

```powershell
flutter run --dart-define=CS_API_URL=https://corestream-app-api-grupo1.vercel.app/api
```

Los proyectos nuevos de Vercel requieren raíces `backend` y `mobile`.
La demo antigua de `main` es independiente; no cambiar su raíz por accidente.
Trasladar código no implica publicar automáticamente otra versión en producción.

## Guías

- [Traslado Supabase → PostgreSQL y Docker](docs/MIGRACION_SUPABASE_POSTGRES.md)
- [PostgreSQL, login e invitaciones](docs/POSTGRES_LOGIN_INVITACIONES.md)
- [Base móvil, pruebas y límites de Vercel](docs/BASE_MOVIL_VERCEL_GRUPO1.md)
- [Requisitos oficiales pendientes](docs/REVISION_REQUISITOS_GRUPO1.md)
- [Desarrollo local](docs/DESARROLLO_LOCAL_GRUPO1.md)
- [RBAC oficial](docs/RBAC.md)
- [README original de CoreStream Web](docs/README_CORESTREAM_WEB_ORIGEN.md)
