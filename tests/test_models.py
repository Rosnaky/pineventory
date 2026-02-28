import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError

from app.db.models import (
    CheckoutRequest,
    CreateItemRequest,
    Item,
    Subteam,
    UpdateItemRequest,
    InventoryStats,
)


# ===== CreateItemRequest Validation =====

class TestCreateItemRequest:
    def test_valid_request(self):
        req = CreateItemRequest(
            item_name="Widget",
            quantity=5,
            location="Shelf A",
            subteam=Subteam("mechanical"),
            point_of_contact=123,
            purchase_order="PO-100",
        ) # type: ignore
        assert req.item_name == "Widget"

    def test_strips_whitespace(self):
        req = CreateItemRequest(
            item_name="  Widget  ",
            quantity=5,
            location="  Shelf A  ",
            subteam=Subteam("mechanical"),
            point_of_contact=123,
            purchase_order="  PO-100  ",
        ) # type: ignore
        assert req.item_name == "Widget"
        assert req.location == "Shelf A"
        assert req.purchase_order == "PO-100"

    def test_quantity_must_be_positive(self):
        with pytest.raises(ValidationError):
            CreateItemRequest(
                item_name="Widget",
                quantity=0,
                location="Lab",
                subteam=Subteam("mechanical"),
                point_of_contact=123,
                purchase_order="PO-1",
            ) # type: ignore

    def test_quantity_negative_fails(self):
        with pytest.raises(ValidationError):
            CreateItemRequest(
                item_name="Widget",
                quantity=-1,
                location="Lab",
                subteam=Subteam("mechanical"),
                point_of_contact=123,
                purchase_order="PO-1",
            ) # type: ignore

    def test_empty_name_fails(self):
        with pytest.raises(ValidationError):
            CreateItemRequest(
                item_name="",
                quantity=5,
                location="Lab",
                subteam=Subteam("mechanical"),
                point_of_contact=123,
                purchase_order="PO-1",
            ) # type: ignore

    def test_empty_location_fails(self):
        with pytest.raises(ValidationError):
            CreateItemRequest(
                item_name="Widget",
                quantity=5,
                location="",
                subteam=Subteam("mechanical"),
                point_of_contact=123,
                purchase_order="PO-1",
            ) # type: ignore

    def test_invalid_subteam_fails(self):
        with pytest.raises(ValueError):
            CreateItemRequest(
                item_name="Widget",
                quantity=5,
                location="Lab",
                subteam=Subteam("invalid_team"),
                point_of_contact=123,
                purchase_order="PO-1",
            ) # type: ignore

    def test_all_subteams_valid(self):
        for team in Subteam:
            req = CreateItemRequest(
                item_name="Widget",
                quantity=1,
                location="Lab",
                subteam=team,
                point_of_contact=123,
                purchase_order="PO-1",
            ) # type: ignore
            assert req.subteam == team


# ===== CheckoutRequest Validation =====

class TestCheckoutRequest:
    def test_valid_request(self):
        req = CheckoutRequest(item_id=1, quantity=3) # type: ignore
        assert req.quantity == 3

    def test_quantity_must_be_positive(self):
        with pytest.raises(ValidationError):
            CheckoutRequest(item_id=1, quantity=0) # type: ignore

    def test_future_return_date_valid(self):
        future = datetime.now() + timedelta(days=7)
        req = CheckoutRequest(item_id=1, quantity=1, expected_return_date=future) # type: ignore
        assert req.expected_return_date == future

    def test_past_return_date_fails(self):
        past = datetime.now() - timedelta(days=1)
        with pytest.raises(ValidationError):
            CheckoutRequest(item_id=1, quantity=1, expected_return_date=past) # type: ignore

    def test_notes_optional(self):
        req = CheckoutRequest(item_id=1, quantity=1) # type: ignore
        assert req.notes is None

    def test_notes_with_content(self):
        req = CheckoutRequest(item_id=1, quantity=1, notes="For testing")
        assert req.notes == "For testing"


# ===== UpdateItemRequest Validation =====

class TestUpdateItemRequest:
    def test_all_fields_optional(self):
        req = UpdateItemRequest() # type: ignore
        assert req.item_name is None
        assert req.quantity_total is None

    def test_partial_update(self):
        req = UpdateItemRequest(item_name="New Name") # type: ignore
        dump = req.model_dump(exclude_unset=True)
        assert "item_name" in dump
        assert "quantity_total" not in dump

    def test_quantity_cannot_be_negative(self):
        with pytest.raises(ValidationError):
            UpdateItemRequest(quantity_total=-1) # type: ignore

    def test_quantity_can_be_zero(self):
        req = UpdateItemRequest(quantity_total=0) # type: ignore
        assert req.quantity_total == 0


# ===== Item Computed Fields =====

class TestItemComputedFields:
    def _make_item(self, total=10, available=7):
        return Item(
            id=1,
            guild_id=1234,
            item_name="Test",
            quantity_total=total,
            quantity_available=available,
            location="Lab",
            subteam=Subteam("mechanical"),
            point_of_contact=123,
            purchase_order="PO-1",
        ) # type: ignore

    def test_quantity_checked_out(self):
        item = self._make_item(total=10, available=7)
        assert item.quantity_checked_out == 3

    def test_quantity_checked_out_zero(self):
        item = self._make_item(total=10, available=10)
        assert item.quantity_checked_out == 0

    def test_is_po_link_true(self):
        item = Item(
            id=1,
            guild_id=1234,
            item_name="Test",
            quantity_total=1,
            quantity_available=1,
            location="Lab",
            subteam=Subteam("mechanical"),
            point_of_contact=123,
            purchase_order="https://discord.com/channels/123/456",
        ) # type: ignore
        assert item.is_po_link is True

    def test_is_po_link_false(self):
        item = self._make_item()
        assert item.is_po_link is False

    def test_available_cannot_exceed_total(self):
        with pytest.raises(ValidationError):
            Item(
                id=1,
                guild_id=1234,
                item_name="Test",
                quantity_total=5,
                quantity_available=10,
                location="Lab",
                subteam=Subteam("mechanical"),
                point_of_contact=123,
                purchase_order="PO-1",
            ) # type: ignore


# ===== InventoryStats =====

class TestInventoryStats:
    def test_utilization_rate(self):
        stats = InventoryStats(
            total_items=10,
            total_quantity=100,
            checked_out_quantity=25,
            active_checkouts=5,
            unique_subteams=3,
        )
        assert stats.utilization_rate == 25.0

    def test_utilization_rate_zero_quantity(self):
        stats = InventoryStats(
            total_items=0,
            total_quantity=0,
            checked_out_quantity=0,
            active_checkouts=0,
            unique_subteams=0,
        )
        assert stats.utilization_rate == 0.0

    def test_utilization_rate_full(self):
        stats = InventoryStats(
            total_items=1,
            total_quantity=10,
            checked_out_quantity=10,
            active_checkouts=1,
            unique_subteams=1,
        )
        assert stats.utilization_rate == 100.0
