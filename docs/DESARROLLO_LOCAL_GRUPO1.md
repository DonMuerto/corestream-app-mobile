# Entorno local del Grupo 1 (Windows)

Este entorno usa el backend oficial sin Supabase, Neon ni servicios de pago.
PostgreSQL 15, Redis 7, FastAPI, el worker ARQ y la web Vue se ejecutan en Docker.
Todos los puertos publicados se limitan a `127.0.0.1`.

## Arranque y uso diario

Instalar Docker Desktop para Windows y abrir el motor de contenedores Linux con
WSL 2. No hace falta una cuenta de Docker para descargar estas imágenes públicas.
Desde la raíz de este repositorio, en PowerShell:

```powershell
.\scripts\local.ps1 Start
.\scripts\local.ps1 Status
```

El script combina los perfiles oficial, dev y local, usa `.env.local.example`
(o `.env.local` si existe) y rechaza destinos de datos no locales y puertos
expuestos fuera del PC. El tercer overlay evita que Compose conserve también
los puertos públicos del perfil de producción. Requiere Compose 2.24.4 o superior.
No copiar `.env.example` de producción para este entorno.

| Componente | Acceso desde el PC |
| --- | --- |
| Web oficial Vue | http://localhost:5173 |
| API FastAPI | http://localhost:8000/api |
| Swagger | http://localhost:8000/api/docs |
| Salud de API y dependencias | http://localhost:8000/api/health |
| PostgreSQL | `localhost:5432`, base `corestream`, usuario `corestream`, contraseña `corestream` |
| Redis | `localhost:6379`, índice 0, sin contraseña |

Las credenciales anteriores son exclusivamente de desarrollo en el PC.
Nunca reutilizarlas en producción ni abrir esos puertos a Internet.

La primera descarga y construcción puede tardar varios minutos. Las siguientes
ejecuciones reutilizan las imágenes y los datos. Mantener espacio libre en el
disco que usa Docker; durante la instalación este PC tenía unos 5 GB libres en C:.

## Primer administrador

```powershell
.\scripts\local.ps1 Admin
```

Correo local por defecto: `admin@corestream.dev`. El script oficial genera una
contraseña aleatoria y la muestra una sola vez. Guardarla antes de cerrar la
terminal. No hay selector de roles ni administrador automático en esta base.
Para otro correo: `.\scripts\local.ps1 Admin -AdminEmail correo@ejemplo.com`.
Los demás usuarios se gestionan desde la aplicación oficial.

En la instalación preparada el 5 de octubre de 2026, el administrador ya fue
creado. Su contraseña quedó en `.env.admin.local`, ignorado por Git. Abrir ese
archivo local para iniciar sesión; no subirlo, compartirlo ni copiarlo al ejemplo.
No volver a ejecutar `Admin` para obtener la contraseña: el script se niega a
crear otro administrador si ya existe uno.

## Comprobaciones y parada

```powershell
.\scripts\local.ps1 Test
.\scripts\local.ps1 Logs
.\scripts\local.ps1 Stop
```

La suite usa la base `corestream_test` y Redis 15, separados del desarrollo.
La base de pruebas se recrea en cada ejecución. `Stop` conserva los datos:
PostgreSQL y Redis usan volúmenes de Docker. No ejecutar `down -v` para detener.
Crear copias de seguridad antes de reiniciar o eliminar esos volúmenes.

## Verificación realizada el 5 de octubre de 2026

- Los cinco contenedores alcanzaron estado saludable.
- PostgreSQL 15.19: 17 tablas y migración Alembic `i5j6k7l8m9n0` aplicada.
- Redis respondió `PONG`; la API confirmó ambas dependencias en estado `ok`.
- La web respondió HTTP 200 y su proxy permitió login y lectura del perfil ADMIN.
- Pruebas unitarias: 159 aprobadas, 2 advertencias.
- Pruebas de integración: 162 aprobadas, 8 `xfail` previstos, 110 advertencias.
- Se comprobó que `corestream` y `corestream_test` son bases diferentes; la base
  de desarrollo conservó su administrador durante las pruebas.

Los ocho `xfail` pertenecen a `backend/tests/integration/test_api_contract.py`:
desajustes ya presentes de métodos, rutas y campos entre Vue y FastAPI (mover
tickets, workbench, analítica, reuniones/asistencia e incidencias). No se
corrigieron en esta instalación. El entorno listo no significa que todas las
funcionalidades de la plataforma ni los requisitos móviles estén completados.
SMTP, traducción y servicios móviles externos no se configuraron aquí.

## Flutter y Vercel

Este arranque prepara la plataforma oficial. No adapta todavía Flutter ni
cambia la demo publicada en Vercel. El futuro cliente local usará la URL
`http://localhost:8000/api` (Android emulado: `http://10.0.2.2:8000/api`).
El origen web reservado para Flutter local es `http://localhost:7357`.
Una URL pública de Vercel no convierte automáticamente esta API local en
un servidor público; esa publicación es un paso separado.
