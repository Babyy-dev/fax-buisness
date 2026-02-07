Project Overview

FAX Order Automation & Document Generation System (MVP)

1. Project Background

The client is a small B2B trading business (fasteners / screws industry).
Currently, orders are received via FAX, and staff manually re-enter data to create:

Packing slips (現品票)

Delivery notes (納品書)

Invoices (請求書)

Each order may contain up to ~200 different products, all requiring individual packing slips.
Product names vary between customer order names and supplier purchase names.

The goal is to reduce manual input work by 70–80% while keeping accuracy high.

2. Project Goal (MVP)

Build a lightweight internal web system that:

Accepts FAX orders as PDF

Uses OCR-assisted input (human confirmation required)

Stores product and pricing knowledge

Automatically generates required PDFs

This is not a full ERP and not fully automatic AI processing.

3. Target Users

1–3 internal users

Non-technical

Desktop browser usage

Japanese language UI

4. System Scope (IN SCOPE)
   4.1 Core Features
   A. Order Intake (Sales)

Upload FAX PDF

OCR extracts:

Product name (text only)

Quantity

Show extracted data in editable table

User can:

Correct text

Select product if not matched

Save as “Sales Order”

B. Product Master

Register products manually

Fields:

Internal product name

Base price (default sales price)

Product aliases:

Multiple names per product

Used for OCR matching

When an unknown product name appears:

User selects product once

Alias is auto-registered

C. Customer & Pricing

Customer master (name only is sufficient)

Customer-specific product pricing:

Default → base price

Override per customer

Automatically remembered for next time

D. Purchase Data (Simple)

Manual purchase entry screen

User selects product and enters purchase price

Purchase price updates base price

No OCR for purchase documents

E. PDF Generation

Generate PDFs using fixed templates:

Packing Slip (現品票)

One PDF per product line

Fields:

Delivery number

Unit number

Product name

Quantity

Delivery Note (納品書)

Invoice (請求書)

Includes unit price and totals

PDF layout should roughly match existing paper forms.

5. Technical Requirements
   Backend

Python 3.10+

FastAPI (or similar lightweight framework)

Frontend

Server-rendered HTML (Jinja2 or equivalent)

Minimal JavaScript

No SPA required

Database

SQLite (initial)

Schema must be migration-ready (PostgreSQL later)

OCR

Cloud OCR (e.g., Google Cloud Vision)

OCR accuracy does not need to be perfect

Human confirmation is mandatory

PDF

HTML → PDF generation

Fixed layout templates

6. Non-Functional Requirements

Simple login (single role is OK)

Data persistence

Manual backup capability

Stable, predictable behavior over automation cleverness

7. Explicitly OUT OF SCOPE (Important)

The following are not included in this project:

Inventory / stock management

Accounting software integration

Supplier master management

Purchase OCR

Fully automatic OCR approval

AI model training

Mobile UI

Multi-role permission system

Performance optimization beyond small-scale usage

Any of the above must be treated as future extensions.

8. Expected Deliverables

Running web application

Source code

Database schema

Basic setup instructions

PDF templates

Short usage explanation (not full manual)

8.1 Expected Output Data

- Structured order data (order, items, quantities, prices)
- Generated PDFs (item labels, delivery note, invoice)
- Updated master data (product base price, customer-specific price)

Note: These outputs are produced after the full workflow completes (upload â†’ OCR/confirm â†’ order save â†’ PDF generation).

9. Output mapping (final PDFs)

The expected outputs after the full process (OCR → confirmation → order save) are:

1) 注文書（兼 納品書 / 請求内訳明細書 / 受領書）
   - Combined order/delivery/invoice detail sheet.
   - Per-line list with product name, quantity, unit price, amount, and barcode blocks.

2) 現品票（Packing Slip）
   - One slip block per product line.
   - Fields: 納品番号 / ユニットNo / 商品名 / 数量.

3) 納品書（Delivery Note）
   - Standard delivery note layout with item list and totals.

4) 納品明細書（Delivery Detail）
   - Detailed delivery list (dates, item codes, quantities, prices, totals).

5) 請求書（Invoice）
   - Standard invoice with header, item table, subtotal/tax/total.

6) 請求明細書（Invoice Detail）
   - Line-level invoice detail list attached to the invoice.

7) 請求書（集計 / 締め用）
   - Statement-style invoice with period totals and carryover.

9. Backend implementation (Python + FastAPI)

- FastAPI exposes `/api/*` endpoints for uploads, order lines, master data, pricing overrides, purchase records, and simulated PDF renders so the React/TS frontend can drive the in-scope workflow from confirmation to document generation.
- SQLModel maps to SQLite (`backend/data/fax.db` by default) with models for products, aliases, customers, pricing, sales orders, order lines, and purchase records; migrations later swap to PostgreSQL/RDS via the `FAX_DB_URL` env var without code changes.
- Uploads land in `backend/uploads/`, each creating a staging `SalesOrder` plus seeded OCR lines for the UI; alias/customer views return lightweight data for JavaScript tables.
- Simple seeding keeps sample customers/products for Japanese desktop users, and helper endpoints (alias suggestions, health check) keep the admin flow discoverable.

10. AWS deployment guidance

- Frontend: build the Vite React+TS site (`npm run build`) and serve via S3 + CloudFront (or Amplify Console) with caching/invalidation conveniences.
- Backend: containerize or deploy FastAPI via ECS/Fargate, App Runner, or Lambda+API Gateway; persist the database on Amazon RDS (PostgreSQL) by setting `FAX_DB_URL`, and store incoming PDFs/preview assets in S3 buckets that also power the `PDF preview` responses.
- OCR: call Google Cloud Vision (or other cloud OCR) from the backend job/post-processing path before writing lines to the database; human confirmation remains mandatory via the React UI.
- Authentication: keep the deployment internal/VPC-only with a single role login (out-of-band password) and manual backup exports for SQLite or RDS snapshots.
