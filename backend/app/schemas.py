from datetime import datetime
from typing import Literal, Optional, List

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
    unit_price: float
    line_total: float
    delivery_number: Optional[str] = None
    unit_number: Optional[str] = None
    notes: Optional[str] = None
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


class SalesOrderRead(SQLModel):
    id: int
    customer_id: Optional[int]
    status: str
    order_number: Optional[str]
    delivery_number: Optional[str]
    invoice_number: Optional[str]
    source_filename: Optional[str]
    stored_path: Optional[str]
    created_at: datetime
    updated_at: datetime
    confirmed_at: Optional[datetime]


class OrderLineUpdate(SQLModel):
    id: int
    product_id: Optional[int]
    normalized_name: str
    quantity: int
    unit_price: float
    delivery_number: Optional[str] = None
    unit_number: Optional[str] = None
    notes: Optional[str] = None
    status: str


class OrderConfirmRequest(SQLModel):
    order_number: Optional[str] = None
    delivery_number: Optional[str] = None
    invoice_number: Optional[str] = None
    lines: List[OrderLineUpdate]


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
    document_type: Literal[
        'order_summary',
        'packing_slip',
        'delivery_note',
        'delivery_detail',
        'invoice',
        'invoice_detail',
        'invoice_statement',
    ]


class PDFRenderResponse(SQLModel):
    order_id: int
    document_type: str
    preview_url: str
    message: str


class DocumentRead(SQLModel):
    id: int
    order_id: int
    document_type: str
    file_path: str
    created_at: datetime


class LoginRequest(SQLModel):
    username: str
    password: str


class LoginResponse(SQLModel):
    token: str
    token_type: str = "bearer"
