# Base móvil oficial del Grupo 1

Esta entrega separa el cliente Flutter de la web Vue. Ambos pueden consumir
el mismo backend FastAPI, pero el entregable del Grupo 1 está en `mobile/`.
No usa la conexión Supabase de la demo anterior. Se trabaja en `desarrollo`;
no se modifica `master` ni se sube código oficial al repositorio público viejo.

## Entornos

- API de desarrollo alojada: https://corestream-app-api-grupo1.vercel.app/api
- Flutter para visualizar en navegador: https://corestream-app-base-grupo1.vercel.app
- PostgreSQL: Neon, recurso `corestream-app-postgres-grupo1`, plan gratuito.
- Redis TLS: Upstash, recurso `corestream-app-redis-grupo1`, plan gratuito,
  con actualizaciones automáticas de plan desactivadas.

La visualización en Vercel es Flutter compilado para Web, no el front Vue.
El mismo código Dart es la base Android. Publicar en Vercel no distribuye
un APK ni demuestra que se haya probado en un dispositivo físico.

## Desarrollo local

Desde la raíz, levantar los servicios oficiales:

```powershell
.\scripts\local.ps1 Start
cd mobile
flutter pub get
flutter run -d chrome --web-port 7357 --dart-define=CS_API_URL=http://localhost:8000/api
```

Para emulador Android, el backend local es `http://10.0.2.2:8000/api`.
Para usar el backend HTTPS de Vercel en Android:

```powershell
flutter run --dart-define=CS_API_URL=https://corestream-app-api-grupo1.vercel.app/api
```

Los administradores local y cloud son independientes. Las credenciales cloud
están únicamente en `backend/.env.cloud.admin.local`, ignorado por Git y por
el despliegue. No usar passwords conocidos ni incorporar cuentas al arranque.
El resto de usuarios se crea mediante las rutas oficiales de invitación o
gestión, no mediante un selector que simula identidades.

## Esquema y secretos

Se aplican las migraciones oficiales del fork y la migración móvil provista
en Drive, encadenada a la revisión actual. Head: `mobile_0001`; 19 tablas
públicas incluyendo `alembic_version`, `user_devices` y `notification_preferences`.
No se usa `create_all`, no se reemplaza el esquema por tablas de demostración.

Las URLs/contraseñas de PostgreSQL/Redis y `SECRET_KEY` se mantienen en el
proyecto API, nunca en variables compiladas de Flutter. La compilación Web
usa `/api` con un proxy de mismo origen hacia FastAPI; Android utiliza la URL
HTTPS de la API. No copiar `.env.vercel.local` al cliente ni a Git.

Operaciones manuales desde `backend/`, con las dependencias oficiales:

```powershell
vercel env pull .env.vercel.local --environment=development
python scripts/cloud_backend.py check
python scripts/cloud_backend.py migrate
python scripts/check_cloud_api.py
```

El check remoto crea un ticket temporal de prueba y lo elimina; compara los
resultados HTTP con las filas de PostgreSQL. Su aplicación/épica de verificación
se conserva como contenedor de pruebas, sin información de clientes.

## Límites explícitos de esta primera base

- FCM, biometría, MFA/SSO, aislamiento por `client_id`, tier/licencias, auditoría
  inmutable y retención/exportación siguen siendo tareas del Grupo 1.
- El cliente usa login real y access token en memoria. El flujo completo de
  refresco/almacenamiento seguro nativo requiere el desarrollo de sesión móvil;
  no se considera implementado por reutilizar el login web.
- En Docker funciona el worker permanente ARQ. En Vercel se mantiene el contrato
  de la cola, pero el consumidor requiere adaptación; no se promete entrega
  push asíncrona por disponer de Redis. Las notificaciones persistidas pueden
  consultarse por la API.
- Carga/descarga de documentos se deshabilita explícitamente en el entorno
  cloud hasta configurar almacenamiento persistente. `/tmp` no guarda archivos
  entre instancias. En Docker se mantiene el volumen oficial.
- La conexión Git automática necesita que la instalación de GitHub de Vercel
  tenga acceso a `josenavarrete666/Corestream_Grupo1`. Los despliegues por CLI
  funcionan independientemente; no confundir esto con CI/CD ya configurado.

## Pruebas

Backend: `pytest tests mobile_api/tests/test_permissions.py`. La suite de
integración usa exclusivamente `corestream_test` y Redis de test; nunca
ejecutarla sobre Neon o sobre una base con datos de usuarios.
La suite de API antigua de `mobile_api/tests/test_api.py` corresponde al
backend de agosto, no al contrato actual; ver README del módulo adaptado.

Flutter: `flutter test` verifica el inicio real. El smoke del selector antiguo
solo se ejecuta con `--dart-define=CS_DEMO=true`, modo explícito de referencia;
no está activo en los despliegues del proyecto.

Para desplegar código fuente: directorio raíz `backend` para la API y `mobile`
para Flutter. `mobile/scripts/build-vercel.sh` instala la versión fijada del SDK.
Alternativa manual: compilar `flutter build web --dart-define=CS_API_URL=/api`,
copiar `vercel.static.json` a `build/web/vercel.json` y publicar esa carpeta con
el mismo proyecto Vercel vinculado. Nunca publicar solo el wireframe HTML.
