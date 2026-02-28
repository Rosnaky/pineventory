import pytest
from app.db.models import CheckoutRequest, CreateItemRequest, Subteam


# ===== Helper =====

async def _create_test_item(db, guild_id=1234, name="Test Item", quantity=10):
    await db.ensure_user_exists(12, "testuser")
    return await db.add_item(
        CreateItemRequest(
            item_name=name,
            quantity=quantity,
            location="Lab",
            subteam=Subteam("mechanical"),
            point_of_contact=12,
            purchase_order="PO 1",
        ), # type: ignore
        guild_id=guild_id,
        added_by=12,
    )


# ===== AUDIT LOG =====

@pytest.mark.asyncio
async def test_log_action(db):
    await db.ensure_user_exists(12, "testuser")

    await db.log_action(1234, 12, "test_action", None, "Test details")

    logs = await db.get_audit_log(limit=10)
    assert len(logs) >= 1
    assert logs[0].action == "test_action"
    assert logs[0].details == "Test details"
    assert logs[0].user_id == 12


@pytest.mark.asyncio
async def test_audit_log_ordering(db):
    await db.ensure_user_exists(12, "testuser")

    await db.log_action(1234, 12, "first", None, "First action")
    await db.log_action(1234, 12, "second", None, "Second action")
    await db.log_action(1234, 12, "third", None, "Third action")

    logs = await db.get_audit_log(limit=10)
    assert len(logs) == 3
    # Most recent first
    assert logs[0].action == "third"
    assert logs[1].action == "second"
    assert logs[2].action == "first"


@pytest.mark.asyncio
async def test_audit_log_limit(db):
    await db.ensure_user_exists(12, "testuser")

    for i in range(10):
        await db.log_action(1234, 12, f"action_{i}", None, f"Detail {i}")

    logs = await db.get_audit_log(limit=5)
    assert len(logs) == 5


@pytest.mark.asyncio
async def test_audit_log_with_item_id(db):
    item = await _create_test_item(db, quantity=1)

    await db.log_action(1234, 12, "custom", item.id, "Item-specific action")

    logs = await db.get_audit_log(limit=1)
    assert logs[0].item_id == item.id


@pytest.mark.asyncio
async def test_full_workflow_audit_trail(db):
    """Verify a complete add -> checkout -> return workflow creates proper audit entries."""
    item = await _create_test_item(db, quantity=5)

    co = await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=2), # type: ignore
        guild_id=1234,
        user_id=12,
    )

    await db.return_item(co.id, guild_id=1234, returned_by=12)

    logs = await db.get_audit_log(limit=10)
    actions = [l.action for l in logs]

    assert "add_item" in actions
    assert "checkout" in actions
    assert "return" in actions
