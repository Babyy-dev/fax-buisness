from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    internal_name: str
    base_price: float
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProductAlias(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id")
    alias_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Customer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    language: Optional[str] = Field(default="ja")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CustomerPricing(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id")
    product_id: int = Field(foreign_key="product.id")
    override_price: float
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SalesOrder(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: Optional[int] = Field(default=None, foreign_key="customer.id")
    status: str = Field(default="staging")
    source_filename: Optional[str] = None
    stored_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OrderLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="salesorder.id")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    customer_name: str
    extracted_text: str
    normalized_name: str
    quantity: int
    status: str = Field(default="needs-review")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PurchaseRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id")
    purchase_price: float
    recorded_at: datetime = Field(default_factory=datetime.utcnow)
    note: Optional[str] = None
