"""
mobile_api — Endpoints de backend para la app móvil de CoreStream.

Paquete autocontenido que implementa la "Especificación de API — CoreStream
Mobile v1.0" sin modificar el código existente:

    - routers/devices.py          §4.1–4.5  Dispositivos y preferencias push (FCM)
    - routers/auth_ext.py         §4.6      Logout con revocación de refresh token
    - routers/mobile.py           §5.1–5.4  Agregados de lectura para móvil (BFF)
    - routers/ticket_assign.py    §6.1      Asignación de tickets
    - routers/websocket_mobile.py §7.1      WebSocket autenticado por JWT
    - migrations/                            Migración Alembic (tablas nuevas + incident_id)
    - patches/                               Cambios documentados a archivos existentes

Integración (ver README.md): copiar esta carpeta a backend/mobile_api y añadir
en app/main.py:

    from mobile_api import include_mobile_routers
    include_mobile_routers(app)
"""

def include_mobile_routers(app):
    """Registra todos los routers del paquete móvil en la aplicación FastAPI."""
    from mobile_api.routers.devices import router as devices_router
    from mobile_api.routers.mobile import router as mobile_router

    # El backend de septiembre ya implementa logout/revocación y WebSocket
    # con tickets de un solo uso. No registrar los adaptadores antiguos que
    # reemplazarían esa seguridad ni duplicar las acciones canónicas.
    app.include_router(devices_router, prefix="/api")
    app.include_router(mobile_router, prefix="/api")
