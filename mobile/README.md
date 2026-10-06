# CoreStream Mobile (Flutter)

App móvil de CoreStream: seguimiento de proyectos, asignación de tareas,
incidencias y notificaciones, **manteniendo los roles y accesos de la versión
web** (ADMIN, TEAM_LEADER, DEVELOPER; GROUP_LEADER en el documento de agosto). Implementa el wireframe funcional
"CoreStream Mobile" y consume la API especificada en
`CoreStream-Mobile-Especificacion-API.docx` (backend FastAPI + paquete
`mobile_api`).

## Arranque rápido

La base incluye Dart, pruebas y plataformas Android/Web. El cliente usa la
API real por defecto. Desde la raíz del repositorio:

```bash
cd mobile
flutter pub get
flutter analyze
flutter test
flutter run --dart-define=CS_API_URL=https://corestream-app-api-grupo1.vercel.app/api
```

La compilación Web fue verificada en Vercel. La repetición de tests Flutter
en este PC está bloqueada por Control de aplicaciones de Windows, que no
se desactivó. Ver pruebas y límites en
[`../docs/BASE_MOVIL_VERCEL_GRUPO1.md`](../docs/BASE_MOVIL_VERCEL_GRUPO1.md).

## Modos de datos

| Modo | Cómo se activa | Qué hace |
|---|---|---|
| **API real** (por defecto) | `flutter run` o `--dart-define=CS_API_URL=.../api` | Login real y datos de PostgreSQL mediante FastAPI. Socket con ticket opaco de un uso, no JWT en la URL. Para Android emulado/local: `http://10.0.2.2:8000/api`. |
| **Demo de referencia** | `flutter run --dart-define=CS_DEMO=true` | Datos ficticios en memoria y selector de usuario. No está activo en la base alojada ni demuestra autenticación. |

## Estructura

```
lib/
├── main.dart                  arranque + MaterialApp (tema oscuro por defecto)
├── providers.dart             Riverpod: sesión, tema, idioma, datos
├── core/
│   ├── config.dart            CS_API_URL / modo demo
│   ├── theme.dart             paleta CoreStream (claro/oscuro) como ThemeExtension
│   └── i18n.dart              ES/EN sin dependencias, formatos de fecha/duración
├── models/models.dart         entidades + enums wire-format + TicketPermissions
├── data/
│   ├── repository.dart        contrato + agregados de vista
│   ├── demo_repository.dart   datos wireframe + simulación push
│   └── api_repository.dart    Dio + WebSocket contra FastAPI
├── services/push_service.dart FCM preparado pero desactivado (compila sin Firebase)
└── ui/                        pantallas y widgets (login, shell, dashboard,
                               proyectos/tablero, detalle ticket + sheets,
                               incidencias, equipo, notificaciones, ajustes)
test/
├── permissions_test.dart      espejo de los tests de permisos del backend
├── demo_repository_test.dart  asignar/completar/pregunta/redirigir/notifs
└── widget_smoke_test.dart     login → dashboard → logout
```

## Roles en la app (igual que la web)

- **ADMIN / GROUP_LEADER**: dashboard global con "Requiere atención", crear y
  asignar tickets, gestionar el ciclo de incidencias, ver carga del equipo.
- **DEVELOPER**: su banco de trabajo, comenzar/completar (con enlace de PR
  validado), plantear pregunta (bloquea y pausa el temporizador), redirigir
  con motivo; el resto en solo lectura.

Los botones se pintan según `TicketPermissions` (espejo exacto de
`mobile_api/services/permission_service.py`); en modo API se usa el bloque
`permissions` que devuelve `GET /mobile/tickets/{id}/detail`, y el servidor
siempre re-valida.

## Activar notificaciones push reales (FCM)

La app compila sin Firebase. Cuando tengáis proyecto de Firebase:

1. `dart pub global activate flutterfire_cli && flutterfire configure`
2. Descomentar `firebase_core` y `firebase_messaging` en `pubspec.yaml`
3. Descomentar `FirebasePushService` en `lib/services/push_service.dart` y
   usarlo en `pushServiceProvider` (providers.dart)
4. El token se registra en el backend con `POST /devices/` ya implementado
   en `ApiRepository.registerDevice`

Detalles del backend (tabla `user_devices`, preferencias, envío) en el
paquete `backend/mobile_api/` y su README.
