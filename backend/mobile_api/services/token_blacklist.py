"""
Revocación de refresh tokens en Redis (§4.6).

El backend actual no emite `jti`, así que la lista de revocados se indexa por
el hash SHA-256 del token. La clave expira exactamente cuando expiraría el
token, de modo que Redis se limpia solo.

IMPORTANTE (parche §4.6 en patches/CAMBIOS_EN_CODIGO_EXISTENTE.md):
el endpoint existente POST /auth/refresh debe llamar a
`is_refresh_token_revoked(...)` antes de emitir tokens nuevos; sin ese
cambio, el logout desactiva el push pero no invalida el refresh token.
"""

import hashlib
import time

from jose import jwt, JWTError

from app.config import get_settings
from app.redis_client import get_redis

_PREFIX = "revoked_refresh:"


def _key(token: str) -> str:
    return _PREFIX + hashlib.sha256(token.encode("utf-8")).hexdigest()


def _decode(token: str) -> dict:
    """Decodifica y valida firma/expiración del refresh token. Lanza JWTError."""
    settings = get_settings()
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


async def revoke_refresh_token(token: str, expected_user_id: str) -> None:
    """
    Marca un refresh token como revocado.

    Args:
        token: Refresh token vigente.
        expected_user_id: `sub` que debe contener el token (el usuario
            autenticado que pide el logout).

    Raises:
        ValueError: Si el token es inválido, expiró o pertenece a otro usuario.
    """
    try:
        payload = _decode(token)
    except JWTError as exc:
        raise ValueError("Refresh token inválido o ya revocado") from exc

    if str(payload.get("sub")) != str(expected_user_id):
        raise ValueError("Refresh token inválido o ya revocado")

    ttl = max(1, int(payload.get("exp", 0) - time.time()))
    redis = await get_redis()
    await redis.set(_key(token), "1", ex=ttl)


async def is_refresh_token_revoked(token: str) -> bool:
    """True si el token figura en la lista de revocados."""
    redis = await get_redis()
    return bool(await redis.exists(_key(token)))
