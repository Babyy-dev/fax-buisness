from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
import uuid
import secrets
import os

import aiofiles
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select, delete

from .db import BASE_DIR, engine, create_db_and_tables, get_session
from .models import (
    Customer,
    CustomerPricing,
    Document,
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
    DocumentRead,
    ExtractedLineRead,
    LoginRequest,
    LoginResponse,
    OrderConfirmRequest,
    PDFRenderRequest,
    PDFRenderResponse,
    ProductAliasCreate,
    ProductAliasRead,
    ProductCreate,
    ProductRead,
    PurchaseRecordCreate,
    PurchaseRecordRead,
    SalesOrderRead,
    UploadResponse,
)
from .pdf_utils import generate_pdf

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = BASE_DIR / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIST_DIR = BASE_DIR.parent / "frontend" / "dist"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"

ADMIN_USER = os.getenv("FAX_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("FAX_ADMIN_PASSWORD", "admin123")
ACTIVE_TOKENS: Dict[str, str] = {}

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

if FRONTEND_ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_ASSETS_DIR)), name="assets")


def require_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.replace("Bearer ", "", 1).strip()
    if token not in ACTIVE_TOKENS:
        raise HTTPException(status_code=401, detail="Invalid token")


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

    products = session.exec(select(Product)).all()
    product_ids = [product.id for product in products if product.id]
    product_price_map = {product.id: product.base_price for product in products if product.id}

    for index, row in enumerate(sample_rows):
        product_id = product_ids[index % len(product_ids)] if product_ids else None
        unit_price = product_price_map.get(product_id, 0.0) if product_id else 0.0
        line_total = unit_price * row["quantity"]
        session.add(
            OrderLine(
                order_id=order_id,
                product_id=product_id,
                customer_name=row["customer_name"],
                extracted_text=row["extracted_text"],
                normalized_name=row["normalized_name"],
                quantity=row["quantity"],
                unit_price=unit_price,
                line_total=line_total,
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


@app.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    if payload.username != ADMIN_USER or payload.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = secrets.token_urlsafe(32)
    ACTIVE_TOKENS[token] = payload.username
    return LoginResponse(token=token)


@app.post("/api/orders/upload", response_model=UploadResponse)
async def upload_order(
    file: UploadFile = File(...),
    customer_id: Optional[int] = Form(None),
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
) -> UploadResponse:
    allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
    original_name = Path(file.filename).name
    suffix = Path(original_name).suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    if customer_id:
        customer = session.get(Customer, customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

    if not suffix:
        suffix = ".pdf"
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
def order_lines(
    order_id: int,
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
) -> List[ExtractedLineRead]:
    order = session.get(SalesOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    lines = session.exec(select(OrderLine).where(OrderLine.order_id == order_id)).all()
    return lines


@app.get("/api/orders", response_model=List[SalesOrderRead])
def list_orders(
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
) -> List[SalesOrderRead]:
    return session.exec(select(SalesOrder).order_by(SalesOrder.created_at.desc())).all()


@app.get("/api/orders/{order_id}", response_model=SalesOrderRead)
def get_order(
    order_id: int,
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
) -> SalesOrderRead:
    order = session.get(SalesOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.post("/api/orders/{order_id}/confirm", response_model=SalesOrderRead)
def confirm_order(
    order_id: int,
    payload: OrderConfirmRequest,
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
) -> SalesOrderRead:
    order = session.get(SalesOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.order_number = payload.order_number or order.order_number
    order.delivery_number = payload.delivery_number or order.delivery_number
    order.invoice_number = payload.invoice_number or order.invoice_number
    order.status = "confirmed"
    order.confirmed_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()

    for line_update in payload.lines:
        line = session.get(OrderLine, line_update.id)
        if not line or line.order_id != order_id:
            continue
        line.product_id = line_update.product_id
        line.normalized_name = line_update.normalized_name
        line.quantity = line_update.quantity
        line.unit_price = line_update.unit_price
        line.line_total = line_update.unit_price * line_update.quantity
        line.delivery_number = line_update.delivery_number
        line.unit_number = line_update.unit_number
        line.notes = line_update.notes
        line.status = line_update.status
        session.add(line)

    session.add(order)
    session.commit()
    session.refresh(order)
    return order


@app.get("/api/products", response_model=List[ProductRead])
def list_products(
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
) -> List[ProductRead]:
    return session.exec(select(Product)).all()


@app.post("/api/products", response_model=ProductRead)
def create_product(
    product: ProductCreate,
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
) -> ProductRead:
    record = Product(**product.dict())
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@app.get("/api/products/aliases", response_model=List[ProductAliasRead])
def list_aliases(
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
) -> List[ProductAliasRead]:
    return session.exec(select(ProductAlias)).all()


@app.post("/api/products/aliases", response_model=ProductAliasRead)
def create_alias(
    alias: ProductAliasCreate,
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
) -> ProductAliasRead:
    product = session.get(Product, alias.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    record = ProductAlias(**alias.dict())
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@app.get("/api/aliases/suggestions")
def alias_suggestions(_auth: None = Depends(require_token)) -> List[dict]:
    return ALIAS_SUGGESTIONS


@app.get("/api/customers", response_model=List[CustomerRead])
def list_customers(
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
) -> List[CustomerRead]:
    return session.exec(select(Customer)).all()


@app.post("/api/customers", response_model=CustomerRead)
def create_customer(
    customer: CustomerCreate,
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
) -> CustomerRead:
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
    _auth: None = Depends(require_token),
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
def list_customer_pricing(
    customer_id: int,
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
) -> List[CustomerPricingRead]:
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    pricing = session.exec(select(CustomerPricing).where(CustomerPricing.customer_id == customer_id)).all()
    return pricing


@app.post("/api/purchases", response_model=PurchaseRecordRead)
def record_purchase(
    purchase: PurchaseRecordCreate,
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
) -> PurchaseRecordRead:
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
def list_purchases(
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
) -> List[PurchaseRecordRead]:
    return session.exec(select(PurchaseRecord)).all()


@app.post("/api/pdf/render", response_model=PDFRenderResponse)
def render_pdf(
    payload: PDFRenderRequest,
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
) -> PDFRenderResponse:
    order = session.get(SalesOrder, payload.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    customer = session.get(Customer, order.customer_id) if order.customer_id else None
    lines = session.exec(select(OrderLine).where(OrderLine.order_id == payload.order_id)).all()
    if customer and lines:
        pricing_rows = session.exec(
            select(CustomerPricing).where(CustomerPricing.customer_id == customer.id)
        ).all()
        pricing_map = {row.product_id: row.override_price for row in pricing_rows}
        product_rows = session.exec(select(Product)).all()
        base_price_map = {row.id: row.base_price for row in product_rows if row.id}
        for line in lines:
            if line.unit_price <= 0:
                if line.product_id and line.product_id in pricing_map:
                    line.unit_price = pricing_map[line.product_id]
                elif line.product_id and line.product_id in base_price_map:
                    line.unit_price = base_price_map[line.product_id]
                line.line_total = line.unit_price * line.quantity
                session.add(line)
        session.commit()
    output_path = generate_pdf(payload.document_type, order, customer, lines, OUTPUT_DIR)

    document = Document(
        order_id=payload.order_id,
        document_type=payload.document_type,
        file_path=str(output_path),
    )
    session.add(document)
    session.commit()
    session.refresh(document)

    preview_url = f"/api/documents/{document.id}/download"
    message = "Document generated."
    return PDFRenderResponse(
        order_id=payload.order_id,
        document_type=payload.document_type,
        preview_url=preview_url,
        message=message,
    )


@app.get("/api/orders/{order_id}/documents", response_model=List[DocumentRead])
def list_documents(
    order_id: int,
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
) -> List[DocumentRead]:
    order = session.get(SalesOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return session.exec(select(Document).where(Document.order_id == order_id)).all()


@app.get("/api/documents/{document_id}/download")
def download_document(
    document_id: int,
    session: Session = Depends(get_session),
    _auth: None = Depends(require_token),
):
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = Path(document.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File missing")
    return FileResponse(file_path, filename=file_path.name)


@app.get("/")
def serve_frontend_root():
    index_path = FRONTEND_DIST_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Frontend not built yet. Run npm run build in frontend/."}


@app.get("/{full_path:path}")
def serve_frontend_spa(full_path: str):
    if full_path.startswith("api") or full_path.startswith("docs") or full_path == "openapi.json":
        raise HTTPException(status_code=404, detail="Not found")
    index_path = FRONTEND_DIST_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend not built yet")
