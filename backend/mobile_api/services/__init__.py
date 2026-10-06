"""
Servicios del módulo móvil.

Importar cada servicio desde su módulo:

    from mobile_api.services.push_service import PushService
    from mobile_api.services.permission_service import compute_ticket_permissions
    from mobile_api.services.token_blacklist import (
        revoke_refresh_token,
        is_refresh_token_revoked,
    )

(Se evita reexportar aquí para que los módulos puros —como
permission_service— sean importables sin el resto del proyecto.)
"""
