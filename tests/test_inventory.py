import pytest
from app.db.models import CreateItemRequest, UpdateItemRequest, Subteam


# ===== ADD ITEM =====

@pytest.mark.asyncio
async def test_add_item(db):
    await db.ensure_user_exists(12, "testuser")

    item = await db.add_item(
        CreateItemRequest(
            item_name="Burgers",
            quantity=5,
            location="A shelf",
            subteam=Subteam("embedded flight software"),
            point_of_contact=12,
            purchase_order="PO 67",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )
    assert item.item_name == "Burgers"
    assert item.quantity_total == 5
    assert item.quantity_available == 5
    assert item.quantity_checked_out == 0
    assert item.location == "A shelf"
    assert item.subteam == Subteam.EFS
    assert item.point_of_contact == 12
    assert item.purchase_order == "PO 67"


@pytest.mark.asyncio
async def test_add_item_creates_audit_log(db):
    await db.ensure_user_exists(12, "testuser")

    item = await db.add_item(
        CreateItemRequest(
            item_name="Servo Motor",
            quantity=3,
            location="Lab",
            subteam=Subteam("mechanical"),
            point_of_contact=12,
            purchase_order="PO 100",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )

    logs = await db.get_audit_log(guild_id=1234, limit=10)
    assert len(logs) >= 1
    latest = logs[0]
    assert latest.action == "add_item"
    assert latest.item_id == item.id
    assert "Servo Motor" in latest.details


@pytest.mark.asyncio
async def test_add_multiple_items_same_guild(db):
    await db.ensure_user_exists(12, "testuser")

    item1 = await db.add_item(
        CreateItemRequest(
            item_name="Widget A",
            quantity=10,
            location="Shelf 1",
            subteam=Subteam("mechanical"),
            point_of_contact=12,
            purchase_order="PO 1",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )
    item2 = await db.add_item(
        CreateItemRequest(
            item_name="Widget B",
            quantity=20,
            location="Shelf 2",
            subteam=Subteam("electrical"),
            point_of_contact=12,
            purchase_order="PO 2",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )

    assert item1.id != item2.id
    items = await db.search_items(1234)
    assert len(items) == 2


@pytest.mark.asyncio
async def test_add_items_different_guilds_isolated(db):
    await db.ensure_user_exists(12, "testuser")

    await db.add_item(
        CreateItemRequest(
            item_name="Guild A Item",
            quantity=5,
            location="Lab",
            subteam=Subteam("mechanical"),
            point_of_contact=12,
            purchase_order="PO 1",
        ), # type: ignore
        guild_id=1111,
        added_by=12,
    )
    await db.add_item(
        CreateItemRequest(
            item_name="Guild B Item",
            quantity=3,
            location="Workshop",
            subteam=Subteam("electrical"),
            point_of_contact=12,
            purchase_order="PO 2",
        ), # type: ignore
        guild_id=2222,
        added_by=12,
    )

    guild_a_items = await db.search_items(1111)
    guild_b_items = await db.search_items(2222)
    assert len(guild_a_items) == 1
    assert len(guild_b_items) == 1
    assert guild_a_items[0].item_name == "Guild A Item"
    assert guild_b_items[0].item_name == "Guild B Item"


# ===== GET ITEM =====

@pytest.mark.asyncio
async def test_get_item(db):
    await db.ensure_user_exists(12, "testuser")

    created = await db.add_item(
        CreateItemRequest(
            item_name="Sensor",
            quantity=8,
            location="Bin 3",
            subteam=Subteam("autonomy"),
            point_of_contact=12,
            purchase_order="PO 55",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )

    fetched = await db.get_item(1234, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.item_name == "Sensor"


@pytest.mark.asyncio
async def test_get_item_wrong_guild_returns_none(db):
    await db.ensure_user_exists(12, "testuser")

    created = await db.add_item(
        CreateItemRequest(
            item_name="Sensor",
            quantity=8,
            location="Bin 3",
            subteam=Subteam("autonomy"),
            point_of_contact=12,
            purchase_order="PO 55",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )

    fetched = await db.get_item(9999, created.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_get_nonexistent_item(db):
    result = await db.get_item(1234, 99999)
    assert result is None


# ===== SEARCH ITEMS =====

@pytest.mark.asyncio
async def test_search_items_by_name(db):
    await db.ensure_user_exists(12, "testuser")

    await db.add_item(
        CreateItemRequest(
            item_name="Arduino Mega",
            quantity=3,
            location="Lab",
            subteam=Subteam("electrical"),
            point_of_contact=12,
            purchase_order="PO 10",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )
    await db.add_item(
        CreateItemRequest(
            item_name="Raspberry Pi",
            quantity=2,
            location="Lab",
            subteam=Subteam("electrical"),
            point_of_contact=12,
            purchase_order="PO 11",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )

    results = await db.search_items(1234, search="Arduino")
    assert len(results) == 1
    assert results[0].item_name == "Arduino Mega"


@pytest.mark.asyncio
async def test_search_items_by_subteam(db):
    await db.ensure_user_exists(12, "testuser")

    await db.add_item(
        CreateItemRequest(
            item_name="Motor",
            quantity=5,
            location="Workshop",
            subteam=Subteam("mechanical"),
            point_of_contact=12,
            purchase_order="PO 20",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )
    await db.add_item(
        CreateItemRequest(
            item_name="Wire",
            quantity=100,
            location="Lab",
            subteam=Subteam("electrical"),
            point_of_contact=12,
            purchase_order="PO 21",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )

    results = await db.search_items(1234, subteam="mechanical")
    assert len(results) == 1
    assert results[0].item_name == "Motor"


@pytest.mark.asyncio
async def test_search_items_by_location(db):
    await db.ensure_user_exists(12, "testuser")

    await db.add_item(
        CreateItemRequest(
            item_name="Bolt Set",
            quantity=50,
            location="Workshop",
            subteam=Subteam("mechanical"),
            point_of_contact=12,
            purchase_order="PO 30",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )
    await db.add_item(
        CreateItemRequest(
            item_name="Capacitor",
            quantity=200,
            location="Lab",
            subteam=Subteam("electrical"),
            point_of_contact=12,
            purchase_order="PO 31",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )

    results = await db.search_items(1234, location="Workshop")
    assert len(results) == 1
    assert results[0].item_name == "Bolt Set"


@pytest.mark.asyncio
async def test_search_items_case_insensitive(db):
    await db.ensure_user_exists(12, "testuser")

    await db.add_item(
        CreateItemRequest(
            item_name="LiPo Battery",
            quantity=10,
            location="Storage",
            subteam=Subteam("electrical"),
            point_of_contact=12,
            purchase_order="PO 40",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )

    results = await db.search_items(1234, search="lipo")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_search_items_no_results(db):
    results = await db.search_items(1234, search="nonexistent")
    assert len(results) == 0


# ===== UPDATE ITEM =====

@pytest.mark.asyncio
async def test_update_item_name(db):
    await db.ensure_user_exists(12, "testuser")

    item = await db.add_item(
        CreateItemRequest(
            item_name="Old Name",
            quantity=5,
            location="Lab",
            subteam=Subteam("mechanical"),
            point_of_contact=12,
            purchase_order="PO 50",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )

    updated = await db.update_item(
        1234, item.id,
        UpdateItemRequest(item_name="New Name"), # type: ignore
        updated_by=12,
    )

    assert updated is not None
    assert updated.item_name == "New Name"
    assert updated.quantity_total == 5  # unchanged


@pytest.mark.asyncio
async def test_update_item_quantity(db):
    await db.ensure_user_exists(12, "testuser")

    item = await db.add_item(
        CreateItemRequest(
            item_name="Resistor Pack",
            quantity=100,
            location="Lab",
            subteam=Subteam("electrical"),
            point_of_contact=12,
            purchase_order="PO 51",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )

    updated = await db.update_item(
        1234, item.id,
        UpdateItemRequest(quantity_total=200), # type: ignore
        updated_by=12,
    )

    assert updated is not None
    assert updated.quantity_total == 200


@pytest.mark.asyncio
async def test_update_item_multiple_fields(db):
    await db.ensure_user_exists(12, "testuser")

    item = await db.add_item(
        CreateItemRequest(
            item_name="Bracket",
            quantity=10,
            location="Workshop",
            subteam=Subteam("mechanical"),
            point_of_contact=12,
            purchase_order="PO 52",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )

    updated = await db.update_item(
        1234, item.id,
        UpdateItemRequest(
            item_name="L-Bracket",
            location="Storage Room",
            subteam=Subteam("operations"),
        ), # type: ignore
        updated_by=12,
    )

    assert updated.item_name == "L-Bracket"
    assert updated.location == "Storage Room"
    assert updated.subteam == Subteam.OPERATIONS


@pytest.mark.asyncio
async def test_update_item_creates_audit_log(db):
    await db.ensure_user_exists(12, "testuser")

    item = await db.add_item(
        CreateItemRequest(
            item_name="Propeller",
            quantity=4,
            location="Hangar",
            subteam=Subteam("mechanical"),
            point_of_contact=12,
            purchase_order="PO 53",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )

    await db.update_item(
        1234, item.id,
        UpdateItemRequest(location="Lab"), # type: ignore
        updated_by=12,
    )

    logs = await db.get_audit_log(guild_id=1234, limit=10)
    edit_logs = [l for l in logs if l.action == "edit_item"]
    assert len(edit_logs) >= 1


@pytest.mark.asyncio
async def test_update_nonexistent_item(db):
    await db.ensure_user_exists(12, "testuser")

    result = await db.update_item(
        1234, 99999,
        UpdateItemRequest(item_name="Ghost"), # type: ignore
        updated_by=12,
    )
    assert result is None


@pytest.mark.asyncio
async def test_update_item_no_changes(db):
    await db.ensure_user_exists(12, "testuser")

    item = await db.add_item(
        CreateItemRequest(
            item_name="Unchanged",
            quantity=1,
            location="Lab",
            subteam=Subteam("autonomy"),
            point_of_contact=12,
            purchase_order="PO 54",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )

    result = await db.update_item(
        1234, item.id,
        UpdateItemRequest(), # type: ignore
        updated_by=12,
    )

    assert result is not None
    assert result.item_name == "Unchanged"


# ===== DELETE ITEM =====

@pytest.mark.asyncio
async def test_delete_item(db):
    await db.ensure_user_exists(12, "testuser")

    item = await db.add_item(
        CreateItemRequest(
            item_name="To Delete",
            quantity=1,
            location="Trash",
            subteam=Subteam("operations"),
            point_of_contact=12,
            purchase_order="PO 60",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )

    success = await db.delete_item(1234, item.id, deleted_by=12)
    assert success is True

    fetched = await db.get_item(1234, item.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_delete_item_creates_audit_log(db):
    await db.ensure_user_exists(12, "testuser")

    item = await db.add_item(
        CreateItemRequest(
            item_name="Audit Delete",
            quantity=1,
            location="Lab",
            subteam=Subteam("mechanical"),
            point_of_contact=12,
            purchase_order="PO 61",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )

    await db.delete_item(1234, item.id, deleted_by=12)

    logs = await db.get_audit_log(guild_id=1234, limit=10)
    delete_logs = [l for l in logs if l.action == "delete_item"]
    assert len(delete_logs) >= 1


@pytest.mark.asyncio
async def test_delete_nonexistent_item(db):
    result = await db.delete_item(1234, 99999, deleted_by=12)
    assert result is False


@pytest.mark.asyncio
async def test_delete_item_wrong_guild(db):
    await db.ensure_user_exists(12, "testuser")

    item = await db.add_item(
        CreateItemRequest(
            item_name="Wrong Guild Delete",
            quantity=1,
            location="Lab",
            subteam=Subteam("mechanical"),
            point_of_contact=12,
            purchase_order="PO 62",
        ), # type: ignore
        guild_id=1234,
        added_by=12,
    )

    result = await db.delete_item(9999, item.id, deleted_by=12)
    assert result is False

    # Item should still exist in original guild
    fetched = await db.get_item(1234, item.id)
    assert fetched is not None