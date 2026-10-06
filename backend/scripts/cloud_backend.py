"""Operaciones manuales sobre los recursos NUEVOS de desarrollo de Grupo 1.

No cambia el .env de Docker, no resetea tablas ni imprime credenciales.
Ejecutar desde backend: python scripts/cloud_backend.py check|migrate|bootstrap.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def check() -> None:
    from sqlalchemy import text

    from app.database import dispose_engine, get_session_maker
    from app.redis_client import close_redis, get_redis, init_redis

    try:
        async with get_session_maker()() as db:
            await db.execute(text("SELECT 1"))
            tables = (await db.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            ))).scalars().all()
            print(f"PostgreSQL conectado; tablas públicas ({len(tables)}): {', '.join(tables)}")
            if "alembic_version" in tables:
                revision = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar()
                print(f"Migración aplicada: {revision}")
        await init_redis()
        assert await (await get_redis()).ping()
        print("Redis TLS: conectado")
    finally:
        await close_redis()
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "migrate", "bootstrap"))
    parser.add_argument("--env-file", default=str(BACKEND / ".env.vercel.local"))
    args = parser.parse_args()
    env_file = Path(args.env_file)
    if not env_file.is_file():
        raise SystemExit("Primero ejecutar vercel env pull .env.vercel.local.")
    load_dotenv(env_file, override=True)
    os.chdir(BACKEND)

    from sqlalchemy.engine import make_url

    url = make_url(os.environ["DATABASE_URL"])
    if not url.host or not url.host.endswith(".neon.tech"):
        raise SystemExit("Protección: este comando solo opera sobre la nueva base Neon.")

    if args.action == "check":
        asyncio.run(check())
    elif args.action == "migrate":
        # Alembic/psycopg2 usa conexión directa; el runtime async usa el pooler.
        direct_url = os.environ.get("DATABASE_URL_UNPOOLED")
        if not direct_url or "-pooler." in (make_url(direct_url).host or ""):
            raise SystemExit("Falta DATABASE_URL_UNPOOLED para migraciones.")
        child_env = dict(os.environ, DATABASE_URL=direct_url)
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                       env=child_env, check=True)
        asyncio.run(check())
    else:
        # Contraseña no publicada ni fija. La recibe de la configuración local
        # ignorada; la herramienta oficial conserva el hash SHA-256 + bcrypt.
        load_dotenv(BACKEND / ".env.cloud.admin.local")
        email = os.environ.get("CLOUD_ADMIN_EMAIL")
        password = os.environ.get("CLOUD_ADMIN_PASSWORD")
        if not email or not password:
            raise SystemExit("Faltan CLOUD_ADMIN_EMAIL/CLOUD_ADMIN_PASSWORD en el entorno local.")
        from app.scripts.create_admin import create_admin
        asyncio.run(create_admin(email, password, "Administrador Grupo 1"))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # No volcar DSN ni los valores de los entornos en la salida del comando.
        print(f"Operación no completada ({type(exc).__name__}). Revisar configuración privada.")
        raise SystemExit(1) from None
