# Fax Order Automation

## Purpose
This project digitizes incoming FAX orders (PDF/image), applies product and pricing rules, and generates final business documents (labels, delivery note, invoice) with SQLite-backed persistence and auditability.

## Stack
- Frontend: React + TypeScript (`frontend`, `frontend-jp`)
- Backend: FastAPI + SQLModel (`backend`)
- OCR: AWS Textract
- Database: SQLite (`backend/data/fax.db`)
- PDF: ReportLab with template backgrounds and Code128 barcodes

## Local run
1. Backend
   - `cd backend`
   - `python -m venv .venv`
   - `.venv\Scripts\activate` (Windows)
   - `pip install -r requirements.txt`
   - `uvicorn app.main:app --reload`
2. Frontend
   - `cd frontend`
   - `npm install`
   - `npm run dev`

## Environment
Create `backend/.env` from `backend/.env.example` and set:
- `AWS_REGION`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `TEXTRACT_S3_BUCKET`
- `TEXTRACT_S3_PREFIX` (optional)
- `CORS_ALLOW_ORIGINS` (comma-separated allowed frontend origins)
- `FAX_ADMIN_USER`
- `FAX_ADMIN_PASSWORD` or `FAX_ADMIN_PASSWORD_HASH`

## Data persistence
All core records are persisted in SQLite:
- `salesorder`, `orderline`, `document`
- `product`, `productalias`
- `customer`, `customerpricing`
- `purchaserecord`
- `ocraudit`, `ocrauditline`

There is no seed/sample data path in runtime upload processing. Uploads are processed from real OCR output.

## API security
- `/api/health` and `/api/auth/login` are public.
- Other `/api/*` endpoints require Bearer token.
- CORS preflight (`OPTIONS`) is allowed.

## Main workflow
1. Upload FAX PDF/image (`POST /api/orders/upload`)
2. OCR extraction + parsing to order lines
3. Product alias/master matching
4. Price application (`customerpricing` fallback to `product.base_price`)
5. Order confirmation (`POST /api/orders/{id}/confirm`)
6. PDF generation (`POST /api/pdf/render`)

## Deployment hardening and backups
- Systemd hardening templates and scripts are in `backend/deploy`.
- Install production services on EC2:
  - `sudo bash /home/ubuntu/<repo>/backend/deploy/install-systemd.sh --app-dir /home/ubuntu/<repo> --user ubuntu`
- Daily SQLite backups are handled by `fax-backup.timer`.
- Manual backup/restore commands are documented in `backend/deploy/README.md`.
