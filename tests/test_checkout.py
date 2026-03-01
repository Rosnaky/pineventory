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


# ===== CHECKOUT =====

@pytest.mark.asyncio
async def test_checkout_basic(db):
    item = await _create_test_item(db, quantity=10)

    checkout = await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=3), # type: ignore
        guild_id=1234,
        user_id=12,
    )

    assert checkout is not None
    assert checkout.quantity == 3
    assert checkout.item_id == item.id
    assert checkout.user_id == 12


@pytest.mark.asyncio
async def test_checkout_reduces_availability(db):
    item = await _create_test_item(db, quantity=10)

    await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=4), # type: ignore
        guild_id=1234,
        user_id=12,
    )

    updated = await db.get_item(1234, item.id)
    assert updated.quantity_available == 6
    assert updated.quantity_checked_out == 4


@pytest.mark.asyncio
async def test_checkout_entire_stock(db):
    item = await _create_test_item(db, quantity=5)

    checkout = await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=5), # type: ignore
        guild_id=1234,
        user_id=12,
    )

    assert checkout is not None
    updated = await db.get_item(1234, item.id)
    assert updated.quantity_available == 0


@pytest.mark.asyncio
async def test_checkout_exceeds_availability_returns_none(db):
    item = await _create_test_item(db, quantity=3)

    result = await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=5), # type: ignore
        guild_id=1234,
        user_id=12,
    )

    assert result is None

    # Quantity should be unchanged
    updated = await db.get_item(1234, item.id)
    assert updated.quantity_available == 3


@pytest.mark.asyncio
async def test_checkout_nonexistent_item(db):
    await db.ensure_user_exists(12, "testuser")

    result = await db.checkout_item(
        CheckoutRequest(item_id=99999, quantity=1), # type: ignore
        guild_id=1234,
        user_id=12,
    )
    assert result is None


@pytest.mark.asyncio
async def test_checkout_wrong_guild(db):
    item = await _create_test_item(db, guild_id=1234, quantity=5)

    result = await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=1), # type: ignore
        guild_id=9999,
        user_id=12,
    )
    assert result is None


@pytest.mark.asyncio
async def test_multiple_checkouts_same_item(db):
    item = await _create_test_item(db, quantity=10)

    await db.ensure_user_exists(13, "user2")

    await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=3), # type: ignore
        guild_id=1234,
        user_id=12,
    )
    await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=4), # type: ignore
        guild_id=1234,
        user_id=13,
    )

    updated = await db.get_item(1234, item.id)
    assert updated.quantity_available == 3
    assert updated.quantity_checked_out == 7


@pytest.mark.asyncio
async def test_checkout_with_notes(db):
    item = await _create_test_item(db, quantity=5)

    checkout = await db.checkout_item(
        CheckoutRequest(
            item_id=item.id,
            quantity=1,
            notes="For the demo on Friday",
        ),
        guild_id=1234,
        user_id=12,
    )

    assert checkout.notes == "For the demo on Friday"


@pytest.mark.asyncio
async def test_checkout_creates_audit_log(db):
    item = await _create_test_item(db, quantity=5)

    await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=2), # type: ignore
        guild_id=1234,
        user_id=12,
    )

    logs = await db.get_audit_log(guild_id=1234, limit=10)
    checkout_logs = [l for l in logs if l.action == "checkout"]
    assert len(checkout_logs) >= 1


# ===== RETURN =====

@pytest.mark.asyncio
async def test_return_item(db):
    item = await _create_test_item(db, quantity=10)

    checkout = await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=4), # type: ignore
        guild_id=1234,
        user_id=12,
    )

    success = await db.return_item(checkout.id, guild_id=1234, returned_by=12)
    assert success is True

    updated = await db.get_item(1234, item.id)
    assert updated.quantity_available == 10
    assert updated.quantity_checked_out == 0


@pytest.mark.asyncio
async def test_return_partial_checkouts(db):
    item = await _create_test_item(db, quantity=10)

    co1 = await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=3), # type: ignore
        guild_id=1234,
        user_id=12,
    )
    co2 = await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=5), # type: ignore
        guild_id=1234,
        user_id=12,
    )

    # Return only the first checkout
    await db.return_item(co1.id, guild_id=1234, returned_by=12)

    updated = await db.get_item(1234, item.id)
    assert updated.quantity_available == 5  # 10 - 5 still out
    assert updated.quantity_checked_out == 5


@pytest.mark.asyncio
async def test_return_already_returned_fails(db):
    item = await _create_test_item(db, quantity=5)

    checkout = await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=2), # type: ignore
        guild_id=1234,
        user_id=12,
    )

    await db.return_item(checkout.id, guild_id=1234, returned_by=12)

    # Try returning again
    result = await db.return_item(checkout.id, guild_id=1234, returned_by=12)
    assert result is False


@pytest.mark.asyncio
async def test_return_nonexistent_checkout(db):
    result = await db.return_item(99999, guild_id=1234, returned_by=12)
    assert result is False


@pytest.mark.asyncio
async def test_return_wrong_guild(db):
    item = await _create_test_item(db, guild_id=1234, quantity=5)

    checkout = await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=2), # type: ignore
        guild_id=1234,
        user_id=12,
    )

    result = await db.return_item(checkout.id, guild_id=9999, returned_by=12)
    assert result is False

    # Item should still be checked out
    updated = await db.get_item(1234, item.id)
    assert updated.quantity_available == 3


@pytest.mark.asyncio
async def test_return_creates_audit_log(db):
    item = await _create_test_item(db, quantity=5)

    checkout = await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=1), # type: ignore
        guild_id=1234,
        user_id=12,
    )

    await db.return_item(checkout.id, guild_id=1234, returned_by=12)

    logs = await db.get_audit_log(guild_id=1234, limit=10)
    return_logs = [l for l in logs if l.action == "return"]
    assert len(return_logs) >= 1


# ===== ACTIVE CHECKOUTS =====

@pytest.mark.asyncio
async def test_get_active_checkouts(db):
    item = await _create_test_item(db, quantity=10)

    await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=2), # type: ignore
        guild_id=1234,
        user_id=12,
    )
    await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=3), # type: ignore
        guild_id=1234,
        user_id=12,
    )

    checkouts = await db.get_active_checkouts(1234)
    assert len(checkouts) == 2


@pytest.mark.asyncio
async def test_get_active_checkouts_excludes_returned(db):
    item = await _create_test_item(db, quantity=10)

    co1 = await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=2), # type: ignore
        guild_id=1234,
        user_id=12,
    )
    await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=3), # type: ignore
        guild_id=1234,
        user_id=12,
    )

    await db.return_item(co1.id, guild_id=1234, returned_by=12)

    checkouts = await db.get_active_checkouts(1234)
    assert len(checkouts) == 1
    assert checkouts[0].quantity == 3


@pytest.mark.asyncio
async def test_get_active_checkouts_by_user(db):
    item = await _create_test_item(db, quantity=10)
    await db.ensure_user_exists(13, "user2")

    await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=2), # type: ignore
        guild_id=1234,
        user_id=12,
    )
    await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=3), # type: ignore
        guild_id=1234,
        user_id=13,
    )

    user12_checkouts = await db.get_active_checkouts(1234, user_id=12)
    assert len(user12_checkouts) == 1
    assert user12_checkouts[0].user_id == 12


@pytest.mark.asyncio
async def test_get_active_checkouts_empty(db):
    checkouts = await db.get_active_checkouts(1234)
    assert len(checkouts) == 0


# ===== ITEM CHECKOUTS =====

@pytest.mark.asyncio
async def test_get_item_checkouts_all(db):
    item = await _create_test_item(db, quantity=10)

    co = await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=2), # type: ignore
        guild_id=1234,
        user_id=12,
    )
    await db.checkout_item(
        CheckoutRequest(item_id=item.id, quantity=3), # type: ignore
        guild_id=1234,
        user_id=12,
    )

    # Return one
    await db.return_item(co.id, guild_id=1234, returned_by=12)

    all_checkouts = await db.get_item_checkouts(1234, item.id, active_only=False)
    assert len(all_checkouts) == 2

    active_only = await db.get_item_checkouts(1234, item.id, active_only=True)
    assert len(active_only) == 1