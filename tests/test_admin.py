import pytest


# ===== USERS =====

@pytest.mark.asyncio
async def test_ensure_user_exists_creates_user(db):
    await db.ensure_user_exists(100, "alice")

    user = await db.get_user(100)
    assert user is not None
    assert user.username == "alice"


@pytest.mark.asyncio
async def test_ensure_user_exists_updates_username(db):
    await db.ensure_user_exists(100, "alice")
    await db.ensure_user_exists(100, "alice_new")

    user = await db.get_user(100)
    assert user.username == "alice_new"


@pytest.mark.asyncio
async def test_get_nonexistent_user(db):
    user = await db.get_user(99999)
    assert user is None


# ===== GUILD MEMBERS =====

@pytest.mark.asyncio
async def test_ensure_guild_member(db):
    await db.ensure_guild_member(1234, 100, "alice")

    user = await db.get_user(100)
    assert user is not None

    perms = await db.get_user_permissions(1234, 100)
    assert perms is not None
    assert perms.is_admin is False


@pytest.mark.asyncio
async def test_ensure_guild_member_idempotent(db):
    await db.ensure_guild_member(1234, 100, "alice")
    await db.ensure_guild_member(1234, 100, "alice")

    perms = await db.get_user_permissions(1234, 100)
    assert perms is not None


# ===== ADMIN PERMISSIONS =====

@pytest.mark.asyncio
async def test_set_admin(db):
    await db.ensure_guild_member(1234, 100, "alice")

    await db.set_admin(1234, 100, True)

    assert await db.is_admin(1234, 100) is True


@pytest.mark.asyncio
async def test_revoke_admin(db):
    await db.ensure_guild_member(1234, 100, "alice")

    await db.set_admin(1234, 100, True)
    await db.set_admin(1234, 100, False)

    assert await db.is_admin(1234, 100) is False


@pytest.mark.asyncio
async def test_is_admin_default_false(db):
    await db.ensure_guild_member(1234, 100, "alice")
    assert await db.is_admin(1234, 100) is False


@pytest.mark.asyncio
async def test_is_admin_nonexistent_user(db):
    assert await db.is_admin(1234, 99999) is False


@pytest.mark.asyncio
async def test_admin_isolated_per_guild(db):
    await db.ensure_guild_member(1111, 100, "alice")
    await db.ensure_guild_member(2222, 100, "alice")

    await db.set_admin(1111, 100, True)

    assert await db.is_admin(1111, 100) is True
    assert await db.is_admin(2222, 100) is False


@pytest.mark.asyncio
async def test_get_guild_admins(db):
    await db.ensure_guild_member(1234, 100, "alice")
    await db.ensure_guild_member(1234, 101, "bob")
    await db.ensure_guild_member(1234, 102, "charlie")

    await db.set_admin(1234, 100, True)
    await db.set_admin(1234, 101, True)
    # charlie is not admin

    admins = await db.get_guild_admins(1234)
    admin_ids = [a.user_id for a in admins]

    assert len(admins) == 2
    assert 100 in admin_ids
    assert 101 in admin_ids
    assert 102 not in admin_ids


@pytest.mark.asyncio
async def test_get_guild_admins_empty(db):
    admins = await db.get_guild_admins(1234)
    assert len(admins) == 0


# ===== GUILD SETTINGS =====

@pytest.mark.asyncio
async def test_upsert_guild_settings(db):
    settings = await db.upsert_guild_settings(1234, "Test Server")

    assert settings.guild_id == 1234
    assert settings.guild_name == "Test Server"
    assert settings.google_sheet_id is None


@pytest.mark.asyncio
async def test_upsert_guild_settings_with_sheet(db):
    settings = await db.upsert_guild_settings(
        1234, "Test Server",
        google_sheet_id="abc123",
        google_sheet_url="https://docs.google.com/spreadsheets/d/abc123",
    )

    assert settings.google_sheet_id == "abc123"
    assert settings.google_sheet_url == "https://docs.google.com/spreadsheets/d/abc123"


@pytest.mark.asyncio
async def test_upsert_guild_settings_preserves_sheet_on_update(db):
    await db.upsert_guild_settings(
        1234, "Test Server",
        google_sheet_id="abc123",
        google_sheet_url="https://example.com",
    )

    # Update just the name, sheet should be preserved
    settings = await db.upsert_guild_settings(1234, "New Name")

    assert settings.guild_name == "New Name"
    assert settings.google_sheet_id == "abc123"


@pytest.mark.asyncio
async def test_get_guild_settings(db):
    await db.upsert_guild_settings(1234, "Test Server")

    settings = await db.get_guild_settings(1234)
    assert settings is not None
    assert settings.guild_name == "Test Server"


@pytest.mark.asyncio
async def test_get_guild_settings_nonexistent(db):
    settings = await db.get_guild_settings(99999)
    assert settings is None


@pytest.mark.asyncio
async def test_set_guild_sheet(db):
    await db.upsert_guild_settings(1234, "Test Server")

    await db.set_guild_sheet(1234, "sheet_id_123", "https://sheets.example.com")

    settings = await db.get_guild_settings(1234)
    assert settings.google_sheet_id == "sheet_id_123"
    assert settings.google_sheet_url == "https://sheets.example.com"
    