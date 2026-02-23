
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, computed_field, field_validator

class Subteam(str, Enum):
    MECHANICAL = "mechanical"
    ELECTRICAL = "electrical"
    EFS = "efs"
    AUTONOMY = "autonomy"
    OPERATIONS = "operations"

class User(BaseModel):
    user_id: int
    username: str
    is_admin: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_record(cls, record):
        return cls(**dict(record))
    

class Item(BaseModel):
    id: int
    item_name: str = Field(min_length=1, max_length=200)
    quantity_total: int = Field(ge=0, description="Total quantity owned")
    quantity_available: int = Field(ge=0, description="Available quantity")
    location: str = Field(min_length=1, max_length=100)
    subteam: Subteam = Field(min_length=1, max_length=100)
    point_of_contact: int = Field(description="Discord user ID")
    purchase_order: str = Field(min_length=1, description="PO number of thread URL")
    description: Optional[str] = Field(None, max_length=1000)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator('quantity_available')
    @classmethod
    def validate_quantity_available(cls, v, info):
        """Ensure available quantity doesn't exceed total"""
        if 'quantity_total' in info.data and v > info.data['quantity_total']:
            raise ValueError('Available quantity cannot exceed total quantity')
        return v
    
    @field_validator('purchase_order')
    @classmethod
    def validate_purchase_order(cls, v):
        """Validate PO format"""
        v = v.strip()
        if not v:
            raise ValueError('Purchase order cannot be empty')
        return v
    
    @computed_field
    @property
    def quantity_checked_out(self) -> int:
        """Calculate how many are currently checked out"""
        return self.quantity_total - self.quantity_available
    
    @computed_field
    @property
    def is_po_link(self) -> bool:
        """Check if purchase order is a Discord link"""
        return self.purchase_order.startswith('https://discord.com/')
    
    @classmethod
    def from_record(cls, record):
        """Create from asyncpg record"""
        return cls(**dict(record))

class CreateItemRequest(BaseModel):
    item_name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(gt=0, description="Initial quantity")
    location: str = Field(min_length=1, max_length=100)
    subteam: Subteam = Field(min_length=1, max_length=100)
    point_of_contact: int = Field(description="Discord user id")
    purchase_order: str = Field(min_length=1)
    description: Optional[str] = Field(None, max_length=1000)

    @field_validator('item_name', 'location', 'subteam', 'purchase_order')
    @classmethod
    def strip_whitespace(cls, v):
        """Strip whitespace from string fields"""
        return v.strip() if isinstance(v, str) else v

class UpdateItemRequest(BaseModel):
    item_name: Optional[str] = Field(None, min_length=1, max_length=200)
    quantity_total: Optional[int] = Field(None, ge=0)
    location: Optional[str] = Field(None, min_length=1, max_length=100)
    subteam: Optional[Subteam] = Field(None, min_length=1, max_length=100)
    point_of_contact: Optional[int] = None
    purchase_order: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = Field(None, max_length=1000)
    
    @field_validator('item_name', 'location', 'subteam', 'purchase_order')
    @classmethod
    def strip_whitespace(cls, v):
        if v is not None and isinstance(v, str):
            return v.strip()
        return v

class Checkout(BaseModel):
    id: int
    item_id: int
    user_id: int = Field(description="Discord user who checked it out")
    quantity: int = Field(gt=0)
    checked_out_at: datetime
    expected_return_date: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=500)
    
    class Config:
        from_attributes = True
    
    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if item is still checked out"""
        return self.returned_at is None
    
    @computed_field
    @property
    def is_overdue(self) -> bool:
        """Check if checkout is overdue"""
        if not self.expected_return_date or self.returned_at:
            return False
        return datetime.now() > self.expected_return_date
    
    @computed_field
    @property
    def days_checked_out(self) -> int:
        """Calculate how many days item has been checked out"""
        end_time = self.returned_at or datetime.now()
        return (end_time - self.checked_out_at).days
    
    @classmethod
    def from_record(cls, record):
        """Create from asyncpg record"""
        return cls(**dict(record))

class CheckoutRequest(BaseModel):
    item_id: int
    quantity: int = Field(gt=0, description="Quantity to check out")
    expected_return_date: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=500)
    
    @field_validator('expected_return_date')
    @classmethod
    def validate_return_date(cls, v):
        """Ensure return date is in the future"""
        if v and v < datetime.now():
            raise ValueError('Expected return date must be in the future')
        return v

class AuditLog(BaseModel):
    id: int
    user_id: int
    action: str = Field(description="Action type: add_item, edit_item, checkout, return, delete_item")
    item_id: Optional[int] = None
    details: str = Field(max_length=500)
    created_at: datetime
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_record(cls, record):
        return cls(**dict(record))

class InventoryStats(BaseModel):
    total_items: int
    total_quantity: int
    checked_out_quantity: int
    active_checkouts: int
    unique_subteams: int
    
    @computed_field
    @property
    def utilization_rate(self) -> float:
        if self.total_quantity == 0:
            return 0.0
        return (self.checked_out_quantity / self.total_quantity) * 100
