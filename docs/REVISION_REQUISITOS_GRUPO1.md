# Revisión de alcance — CoreStream App, Equipo 1

Contraste del 2026-10-06: base para empezar el desarrollo, no entrega final
ni declaración de cumplimiento total del Grupo 1.

## Fuentes revisadas

- [Especificación móvil de API, 27-08-2026](https://docs.google.com/document/d/1Qdg1CxJB3fxtR_8vM-V_rh45MRJfCHqZ/edit).
- [Estándares transversales y capacidades comerciales](https://docs.google.com/document/d/1kZb-exdDLqF2iocVPA6wUd5CgHC0W5or/edit), consultados nuevamente en Drive.
- [Equipo 1 — Sesión, Seguridad y Plataforma, 05-09-2026](https://docs.google.com/document/d/1X_W7Va_M6ZNyL4QwbvGMwnbxiimAer3X/edit).
- Flutter y `mobile_api` entregados; backend compartido del fork hasta
  `94cb390`, sus contratos, modelos, permisos y pruebas.

Las grabaciones MP4 no se han transcrito/revisado íntegramente. Si contienen
cambios posteriores, requieren contraste adicional. Los documentos son fuentes
de requisitos, no autorización para publicar secretos o alterar permisos/datos.

## Arquitectura reutilizada

La API móvil agrega dispositivos y lecturas optimizadas al mismo FastAPI,
PostgreSQL y dominio de CoreStream Web. No reemplaza ese backend por otro.
El documento de agosto usa `GROUP_LEADER` y `DONE`; el backend actual usa
`TEAM_LEADER` y `COMPLETED`. Flutter fue adaptado al contrato real.

El WebSocket utiliza el ticket opaco de un uso del backend, no JWT en URL
como proponía agosto. Neon usa Alembic oficial más la migración de dispositivos,
no datos mock ni tablas simplificadas de la Ficha de Duoc.

## Requerimientos asignados

| Código | Estado actual | Pendiente |
|---|---|---|
| TRV-01: multi-tenancy | No desarrollado | `client_id` obligatorio/indexado, autorización por tenant en todos los endpoints y pruebas cross-tenant. |
| TRV-02: feature gating | No desarrollado | Plan comercial, flags, restricciones 403/402 y visibilidad dinámica en la app. |
| TRV-07: auditoría de no repudio | No desarrollado | Logs inmutables de quién/qué/cuándo/IP/User-Agent/resultado en un motor especializado. Los eventos de tickets no lo sustituyen. |
| TRV-08: retención/exportación | No desarrollado | Retención por plan y exportación Enterprise; depende de TRV-02/TRV-07. |
| APP-03: cierre de sesión | Parcial | Backend revoca y comprueba tokens en Redis. Completar refresh/almacenamiento seguro móvil, desactivación del dispositivo y pruebas de logout con FCM real. |
| APP-06: push FCM | Pendiente de integración real | Rutas/tablas y servicio de referencia presentes. Faltan Firebase, cliente, deep links, pruebas y ejecución asíncrona fiable en alojamiento. |
| NEW-08: MFA/SSO | No desarrollado | TOTP/política por cliente y proveedores externos con los mismos roles/aislamiento. |
| NEW-10: biometría | No desarrollado | Desbloquear solo sesiones ya autenticadas, fallback de contraseña y prueba en dispositivos. |

## Invitaciones y sesión

El backend elimina registro público y permite invitaciones con correo, rol,
expiración y aceptación de un uso. No precarga las cuentas del equipo.
Hay un administrador inicial en Neon. Flutter usa login real, pero no tiene
pantallas de invitación/aceptación ni SMTP configurado.
Ver [PostgreSQL, login e invitaciones](POSTGRES_LOGIN_INVITACIONES.md).

## Límites de despliegue

- Vercel visualiza Flutter Web: no demuestra APK probado ni funciones nativas.
- Docker tiene worker ARQ permanente. Redis alojado no instala ese consumidor
  en Vercel: adaptar ejecución antes de prometer entrega push asíncrona.
- Documentos/archivos requieren almacenamiento persistente cloud.
- El código trasladado incluye el socket directo corregido; una actualización
  en producción requiere otro despliegue, no solo el traslado del repositorio.

Pruebas realizadas y limitaciones:
[Base móvil de Vercel](BASE_MOVIL_VERCEL_GRUPO1.md).

Al trasladar la base se repitieron las suites `test_invitations.py` y
`test_auth.py`: 33 pruebas aprobadas contra PostgreSQL local `corestream_test`
y Redis de pruebas, no Neon. Se verificó además la equivalencia de los 392
archivos oficiales, salvo guías/reglas de Git y normalización de finales de línea.
