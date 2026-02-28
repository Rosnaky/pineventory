# ===== Helper =====

import pytest

from app.db.models import CheckoutRequest, CreateItemRequest, Subteam


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


@pytest.mark.asyncio
async def test_stats_empty(db):
    stats = await db.get_stats()

    assert stats.total_items == 0
    assert stats.total_quantity == 0
    assert stats.checked_out_quantity == 0
    assert stats.active_checkouts == 0
    assert stats.utilization_rate == 0.0


@pytest.mark.asyncio
async def test_stats_with_items(db):
    await _create_test_item(db, name="Item A", quantity=10)
    await _create_test_item(db, name="Item B", quantity=20)

    stats = await db.get_stats()

    assert stats.total_items == 2
    assert stats.total_quantity == 30
    assert stats.checked_out_quantity == 0


@pytest.mark.asyncio
async def test_stats_with_checkouts(db):
    item = await _create_test_item(db, quantity=10)

    await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=4), # type: ignore
        guild_id=1234,
        user_id=12,
    )

    stats = await db.get_stats()

    assert stats.total_items == 1
    assert stats.total_quantity == 10
    assert stats.checked_out_quantity == 4
    assert stats.active_checkouts == 1
    assert stats.utilization_rate == 40.0


@pytest.mark.asyncio
async def test_stats_after_return(db):
    item = await _create_test_item(db, quantity=10)

    co = await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=4), # type: ignore
        guild_id=1234,
        user_id=12,
    )

    await db.return_item(co.id, guild_id=1234, returned_by=12)

    stats = await db.get_stats()

    assert stats.checked_out_quantity == 0
    assert stats.active_checkouts == 0
    assert stats.utilization_rate == 0.0
