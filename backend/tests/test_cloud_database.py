"""Conexión remota sin exponer DSN y sin afectar los valores de Docker."""
import ssl
from unittest.mock import patch

from sqlalchemy.pool import NullPool

from app.config import Settings
from app.database import _build_engine


def test_provider_urls_are_normalized():
    for scheme in ("postgres://", "postgresql://"):
        value = Settings(DATABASE_URL=f"{scheme}test:test@localhost/test", _env_file=None)
        assert value.DATABASE_URL.startswith("postgresql+asyncpg://")


def test_neon_tls_and_serverless_pool(monkeypatch):
    monkeypatch.setenv("DB_NULL_POOL", "true")
    from app.config import get_settings
    get_settings.cache_clear()
    try:
        with patch("app.database.create_async_engine") as factory:
            _build_engine("postgresql+asyncpg://user:pass@host.neon.tech/db?sslmode=require&channel_binding=require")
            url = factory.call_args.args[0]
            options = factory.call_args.kwargs
            assert "sslmode" not in url.query
            assert "channel_binding" not in url.query
            assert options["poolclass"] is NullPool
            tls = options["connect_args"]["ssl"]
            assert isinstance(tls, ssl.SSLContext)
            assert tls.check_hostname and tls.verify_mode == ssl.CERT_REQUIRED
            assert options["connect_args"]["statement_cache_size"] == 0
            assert options["connect_args"]["prepared_statement_cache_size"] == 0
            assert "pool_size" not in options
    finally:
        get_settings.cache_clear()


def test_sqlite_does_not_receive_postgres_options():
    with patch("app.database.create_async_engine") as factory:
        _build_engine("sqlite+aiosqlite:///:memory:")
        assert "connect_args" not in factory.call_args.kwargs
        assert "pool_size" not in factory.call_args.kwargs
