"""
Infraestructura de tests de integración del módulo móvil.

Los tests de API necesitan PostgreSQL (los modelos usan tipos nativos de PG).
Se activan definiendo TEST_DATABASE_URL, por ejemplo con la BD del
docker-compose del proyecto:

    export TEST_DATABASE_URL=postgresql+asyncpg://corestream:corestream@localhost:5432/corestream_test

Sin la variable, los tests de API se omiten (los de permisos corren siempre).
La autenticación se simula sobreescribiendo la dependencia get_current_user,
de modo que cada test elige el rol con el que llama a la API.
"""

import os
import uuid

import pytest
import pytest_asyncio

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")

requires_db = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="Defina TEST_DATABASE_URL (PostgreSQL) para ejecutar los tests de API",
)


@pytest_asyncio.fixture(scope="function")
async def ctx():
    """
    Contexto de test: engine + tablas + usuarios de los 3 roles + app FastAPI
    con los routers móviles y las dependencias sobreescritas.

    Devuelve un objeto con: app, session_factory, users (dict por rol),
    y set_current_user(user) para elegir la identidad de las peticiones.
    """
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import app.models  # registra todos los modelos existentes en Base
    import mobile_api.models  # registra user_devices / notification_preferences
    from app.database import get_db
    from app.middleware.auth import get_current_user, hash_password
    from app.models.base import Base
    from app.models import User
    from app.schemas import TokenPayload
    from mobile_api import include_mobile_routers

    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # --- usuarios de prueba (emails únicos por ejecución) ---
    run_id = uuid.uuid4().hex[:8]
    users = {}
    async with session_factory() as session:
        for role in ("ADMIN", "GROUP_LEADER", "DEVELOPER"):
            user = User(
                email=f"test.{role.lower()}.{run_id}@wellq.test",
                hashed_password=hash_password("Secreto123!"),
                full_name=f"Test {role.title()} {run_id}",
                role=role,
                is_active=True,
            )
            session.add(user)
            users[role] = user
        await session.commit()
        for user in users.values():
            await session.refresh(user)

    # --- app de test con dependencias sobreescritas ---
    test_app = FastAPI()
    include_mobile_routers(test_app)

    current = {"user": users["ADMIN"]}

    async def override_get_db():
        async with session_factory() as session:
            yield session

    async def override_get_current_user():
        u = current["user"]
        return TokenPayload(sub=str(u.id), role=str(getattr(u.role, "value", u.role)), exp=2_000_000_000)

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_current_user] = override_get_current_user

    class Ctx:
        pass

    c = Ctx()
    c.app = test_app
    c.session_factory = session_factory
    c.users = users

    def set_current_user(user):
        current["user"] = user

    c.set_current_user = set_current_user

    yield c

    # --- limpieza ---
    # Primero las aplicaciones de prueba (cascada: épicas -> tickets -> eventos).
    # Es necesario antes de borrar usuarios: ticket_events.user_id es NOT NULL
    # con FK ON DELETE SET NULL (inconsistencia del modelo existente), así que
    # borrar un usuario con eventos vivos violaría la restricción.
    from sqlalchemy import delete as _delete, select as _select
    from app.models import Application as _Application, Notification as _Notification
    async with session_factory() as session:
        user_ids = [u.id for u in users.values()]
        # notifications.user_id sufre la misma inconsistencia NOT NULL + SET NULL
        await session.execute(_delete(_Notification).where(_Notification.user_id.in_(user_ids)))
        apps = (await session.execute(
            _select(_Application).where(_Application.owner_id.in_(user_ids))
        )).scalars().all()
        for a in apps:
            await session.delete(a)
        await session.commit()
        for user in users.values():
            db_user = await session.get(User, user.id)
            if db_user is not None:
                await session.delete(db_user)
        await session.commit()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(ctx):
    """Cliente HTTP async contra la app de test."""
    import httpx

    transport = httpx.ASGITransport(app=ctx.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
