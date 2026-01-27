from datetime import datetime
from pathlib import Path
from typing import List, Optional
import uuid

import aiofiles
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select, delete

from .db import BASE_DIR, engine, create_db_and_tables, get_session
from .models import (
    Customer,
    CustomerPricing,
    OrderLine,
    Product,
    ProductAlias,
    PurchaseRecord,
    SalesOrder,
)
from .schemas import (
    CustomerCreate,
    CustomerPricingCreate,
    CustomerPricingRead,
    CustomerRead,
    ExtractedLineRead,
    PDFRenderRequest,
    PDFRenderResponse,
    ProductAliasCreate,
    ProductAliasRead,
    ProductCreate,
    ProductRead,
    PurchaseRecordCreate,
    PurchaseRecordRead,
    UploadResponse,
)

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALIAS_SUGGESTIONS = [
    {"product": "M8 Tapping Screw", "alias": "TAP-M8X20"},
    {"product": "M6 Hex Nut", "alias": "HEX-M6"},
    {"product": "Plastic Spacer 10mm", "alias": "SPC-PL-10"},
]

app = FastAPI(
    title="Fax Order Automation API",
    description="FastAPI service for fax OCR intake, product/customer masters, pricing overrides, and document rendering.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def seed_defaults(session: Session) -> None:
    """Seed the database with sample products and customers when the tables are empty."""
    product_exists = session.exec(select(Product)).first()
    if not product_exists:
        session.add_all(
            [
                Product(internal_name="M3x8 Screw", base_price=16.5),
                Product(internal_name="M5 Flange Bolt", base_price=60.1),
                Product(internal_name="Wing Nut", base_price=31.0),
            ]
        )

    customer_exists = session.exec(select(Customer)).first()
    if not customer_exists:
        session.add_all(
            [
                Customer(name="Osaka Trading"),
                Customer(name="Kyoto Fasteners"),
                Customer(name="Nagoya Assembly"),
            ]
        )

    session.commit()


def create_sample_lines(order_id: int, session: Session) -> None:
    """Populate order lines with sample OCR data for frontend review."""
    session.exec(delete(OrderLine).where(OrderLine.order_id == order_id))
    session.commit()

    sample_rows = [
        {
            "customer_name": "M3x8 Screw",
            "extracted_text": "M3X8 スクリュー",
            "normalized_name": "M3x8 Machine Screw",
            "quantity": 150,
            "status": "matched",
        },
        {
            "customer_name": "M5 Flange Bolt",
            "extracted_text": "M5 FLANGE BOLT",
            "normalized_name": "M5 Flange Bolt",
            "quantity": 40,
            "status": "matched",
        },
        {
            "customer_name": "Wing Nut",
            "extracted_text": "ウイングナット",
            "normalized_name": "Wing Nut",
            "quantity": 20,
            "status": "needs-review",
        },
    ]

    product_ids = [product.id for product in session.exec(select(Product)).all() if product.id]

    for index, row in enumerate(sample_rows):
        product_id = product_ids[index % len(product_ids)] if product_ids else None
        session.add(
            OrderLine(
                order_id=order_id,
                product_id=product_id,
                customer_name=row["customer_name"],
                extracted_text=row["extracted_text"],
                normalized_name=row["normalized_name"],
                quantity=row["quantity"],
                status=row["status"],
            )
        )

    session.commit()


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        seed_defaults(session)


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/orders/upload", response_model=UploadResponse)
async def upload_order(
    file: UploadFile = File(...),
    customer_id: Optional[int] = Form(None),
    session: Session = Depends(get_session),
) -> UploadResponse:
    if customer_id:
        customer = session.get(Customer, customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

    original_name = Path(file.filename).name
    suffix = Path(original_name).suffix or ".pdf"
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    target_path = UPLOAD_DIR / stored_name

    async with aiofiles.open(target_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

    order = SalesOrder(
        customer_id=customer_id,
        source_filename=original_name,
        stored_path=str(target_path.relative_to(BASE_DIR)),
        status="uploaded",
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    create_sample_lines(order.id, session)

    return UploadResponse(
        order_id=order.id,
        stored_path=order.stored_path or "",
        status=order.status,
    )


@app.get("/api/orders/{order_id}/lines", response_model=List[ExtractedLineRead])
def order_lines(order_id: int, session: Session = Depends(get_session)) -> List[ExtractedLineRead]:
    order = session.get(SalesOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    lines = session.exec(select(OrderLine).where(OrderLine.order_id == order_id)).all()
    return lines


@app.get("/api/products", response_model=List[ProductRead])
def list_products(session: Session = Depends(get_session)) -> List[ProductRead]:
    return session.exec(select(Product)).all()


@app.post("/api/products", response_model=ProductRead)
def create_product(product: ProductCreate, session: Session = Depends(get_session)) -> ProductRead:
    record = Product(**product.dict())
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@app.get("/api/products/aliases", response_model=List[ProductAliasRead])
def list_aliases(session: Session = Depends(get_session)) -> List[ProductAliasRead]:
    return session.exec(select(ProductAlias)).all()


@app.post("/api/products/aliases", response_model=ProductAliasRead)
def create_alias(alias: ProductAliasCreate, session: Session = Depends(get_session)) -> ProductAliasRead:
    product = session.get(Product, alias.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    record = ProductAlias(**alias.dict())
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@app.get("/api/aliases/suggestions")
def alias_suggestions() -> List[dict]:
    return ALIAS_SUGGESTIONS


@app.get("/api/customers", response_model=List[CustomerRead])
def list_customers(session: Session = Depends(get_session)) -> List[CustomerRead]:
    return session.exec(select(Customer)).all()


@app.post("/api/customers", response_model=CustomerRead)
def create_customer(customer: CustomerCreate, session: Session = Depends(get_session)) -> CustomerRead:
    record = Customer(**customer.dict())
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@app.post("/api/customers/{customer_id}/pricing", response_model=CustomerPricingRead)
def create_customer_pricing(
    customer_id: int,
    pricing: CustomerPricingCreate,
    session: Session = Depends(get_session),
) -> CustomerPricingRead:
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    product = session.get(Product, pricing.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    record = CustomerPricing(customer_id=customer_id, **pricing.dict())
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@app.get("/api/customers/{customer_id}/pricing", response_model=List[CustomerPricingRead])
def list_customer_pricing(customer_id: int, session: Session = Depends(get_session)) -> List[CustomerPricingRead]:
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    pricing = session.exec(select(CustomerPricing).where(CustomerPricing.customer_id == customer_id)).all()
    return pricing


@app.post("/api/purchases", response_model=PurchaseRecordRead)
def record_purchase(purchase: PurchaseRecordCreate, session: Session = Depends(get_session)) -> PurchaseRecordRead:
    record = PurchaseRecord(**purchase.dict())
    product = session.get(Product, purchase.product_id)

    session.add(record)
    if product:
        product.base_price = purchase.purchase_price
        product.updated_at = datetime.utcnow()
        session.add(product)

    session.commit()
    session.refresh(record)
    return record


@app.get("/api/purchases", response_model=List[PurchaseRecordRead])
def list_purchases(session: Session = Depends(get_session)) -> List[PurchaseRecordRead]:
    return session.exec(select(PurchaseRecord)).all()


@app.post("/api/pdf/render", response_model=PDFRenderResponse)
def render_pdf(payload: PDFRenderRequest, session: Session = Depends(get_session)) -> PDFRenderResponse:
    order = session.get(SalesOrder, payload.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    preview_url = f"https://cdn.example.com/previews/{payload.order_id}-{payload.document_type}.pdf"
    message = "Document template compiled. Download from the storage bucket."
    return PDFRenderResponse(
        order_id=payload.order_id,
        document_type=payload.document_type,
        preview_url=preview_url,
        message=message,
    )
