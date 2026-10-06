# CoreStream Mobile (Flutter)

App móvil de CoreStream: seguimiento de proyectos, asignación de tareas,
incidencias y notificaciones, **manteniendo los roles y accesos de la versión
web** (ADMIN, GROUP_LEADER, DEVELOPER). Implementa el wireframe funcional
"CoreStream Mobile" y consume la API especificada en
`CoreStream-Mobile-Especificacion-API.docx` (backend FastAPI + paquete
`mobile_api`).

## Arranque rápido

Este paquete contiene solo el código Dart (lib/, test/, pubspec). Las carpetas
de plataforma (android/, ios/) se generan con `flutter create` — es el flujo
estándar para distribuir código Flutter sin binarios:

```bash
cd corestream_mobile
flutter create --org co.wellq --project-name corestream_mobile .
flutter pub get
flutter analyze          # debe salir limpio
flutter test             # permisos + repositorio demo + smoke de UI
flutter run              # arranca en MODO DEMO (sin servidor)
```

> Verificación pendiente en tu máquina: este código se escribió y revisó sin
> acceso al SDK de Flutter (la red del entorno de desarrollo no permite
> descargarlo), así que `flutter analyze` y `flutter test` son el primer paso
> obligatorio. Cualquier aviso del analyzer debería ser menor.

## Modos de datos

| Modo | Cómo se activa | Qué hace |
|---|---|---|
| **Demo** (por defecto) | `flutter run` | Datos del wireframe en memoria, selector de rol en el login, y simulación de eventos del equipo cada ~20 s (nueva incidencia, ticket asignado, completado, pregunta) que llegan como toasts push + campana. Nada se guarda. |
| **API real** | `flutter run --dart-define=CS_API_URL=http://10.0.2.2:8000` | Cliente Dio contra el backend FastAPI: `/mobile/*` (BFF), acciones de tickets, incidencias, notificaciones y WebSocket autenticado `/ws/mobile/notifications?token=`. `10.0.2.2` es localhost visto desde el emulador Android. |

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
