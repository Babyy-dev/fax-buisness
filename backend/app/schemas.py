from datetime import datetime
from typing import Literal, Optional

from sqlmodel import SQLModel


class UploadResponse(SQLModel):
    order_id: int
    stored_path: str
    status: str


class ExtractedLineRead(SQLModel):
    id: int
    order_id: int
    product_id: Optional[int]
    customer_name: str
    extracted_text: str
    normalized_name: str
    quantity: int
    status: str


class ProductBase(SQLModel):
    internal_name: str
    base_price: float
    description: Optional[str] = None


class ProductCreate(ProductBase):
    pass


class ProductRead(ProductBase):
    id: int


class ProductAliasCreate(SQLModel):
    product_id: int
    alias_name: str


class ProductAliasRead(ProductAliasCreate):
    id: int


class CustomerCreate(SQLModel):
    name: str
    language: Optional[str] = "ja"


class CustomerRead(CustomerCreate):
    id: int


class CustomerPricingCreate(SQLModel):
    product_id: int
    override_price: float


class CustomerPricingRead(CustomerPricingCreate):
    id: int
    customer_id: int
    created_at: datetime


class PurchaseRecordCreate(SQLModel):
    product_id: int
    purchase_price: float
    note: Optional[str] = None


class PurchaseRecordRead(PurchaseRecordCreate):
    id: int
    recorded_at: datetime


class PDFRenderRequest(SQLModel):
    order_id: int
    document_type: Literal['packing', 'delivery', 'invoice']


class PDFRenderResponse(SQLModel):
    order_id: int
    document_type: str
    preview_url: str
    message: str
