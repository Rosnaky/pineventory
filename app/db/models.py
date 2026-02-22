
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, computed_field, field_validator

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
    subteam: str = Field(min_length=1, max_length=100)
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
