# tests/conftest.py
import os
import sys
from pathlib import Path
from app.db.db_manager import DatabaseManager
from app.db.migrations.migrate import MigrationManager

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

TEST_DB_URL = os.getenv(
    "TEST_DB_URL",
    "postgresql://test:test@localhost:5433/pineventory_test"
)

@pytest.fixture
async def db():
    migrator = MigrationManager(TEST_DB_URL)
    await migrator.run_migrations()

    manager = DatabaseManager(TEST_DB_URL)
    await manager.connect()

    yield manager

    if not manager.pool:
        return

    async with manager.pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE audit_log, checkouts, items, guild_permissions, guild_settings, users CASCADE"
        )

    await manager.close()