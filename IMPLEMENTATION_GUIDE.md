Implementation Guide

This guide explains how to run the project end-to-end with real OCR (AWS Textract),
SQLite persistence, and PDF generation using background templates.

Contents
1) Architecture summary
2) Local setup
3) OCR setup (AWS Textract)
4) Background templates + fonts
5) Database persistence + audit
6) Local test flow
7) EC2 deployment (single instance)
8) Troubleshooting

---

1) Architecture summary
- Backend: FastAPI (Python)
- DB: SQLite (backend/data/fax.db)
- OCR: AWS Textract (images and PDFs)
- PDF generation: ReportLab, Code128 barcodes, background templates
- Frontend: React + TypeScript (served by backend if desired)

Scope summary
When a customer sends an order by FAX, the document is saved as a PDF or image, then read by the system to extract product names, quantities, and customer details. Product names are matched to internal masters even when they differ in wording. Prices are applied automatically based on standard prices or the last customer-specific price. The order is saved as a sales record, and the system generates item labels, delivery notes, and invoices without manual re-entry. Over time, purchases and sales improve price accuracy and matching.

Post-OCR Goals
- Persist structured sales data (`salesorder`, `orderline`) from OCR output.
- Auto-apply pricing from customer override or product base price.
- Persist OCR audit artifacts (`ocraudit`, `ocrauditline`) for traceability.
- Generate final business PDFs from confirmed order data.
- Improve future matching and pricing accuracy through alias/pricing/purchase history.

---

2) Local setup
Prereqs:
- Python 3.10+
- Node 18+

Environment (optional, recommended):
- Copy `backend/.env.example` to `backend/.env`
- Fill in AWS keys, Textract bucket, and any overrides
Security settings:
- Use `FAX_ADMIN_PASSWORD_HASH` instead of plain password for production.
- Set `CORS_ALLOW_ORIGINS` to your frontend domain(s), comma-separated.
- Token expiry controlled by `FAX_TOKEN_TTL_MINUTES`.

Generate a password hash (PowerShell):
  python -c "import os,base64,hashlib; password='your-strong-password'; salt=os.urandom(16); iterations=200000; dk=hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations); print(f'pbkdf2${iterations}$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(dk).decode())"

Install backend deps:
  cd backend
  python -m venv .venv
  .venv\\Scripts\\activate   (Windows)
  pip install -r requirements.txt

Install frontend deps:
  cd frontend
  npm install

Run backend:
  cd backend
  uvicorn app.main:app --reload

Run frontend (optional dev server):
  cd frontend
  npm run dev

---

3) OCR setup (AWS Textract)
AWS required for real OCR:
- AWS_REGION (ex: ap-northeast-1)
- TEXTRACT_S3_BUCKET (required for PDF OCR)
- TEXTRACT_S3_PREFIX (optional, default: textract)

Example (PowerShell):
  $env:AWS_REGION="ap-northeast-1"
  $env:TEXTRACT_S3_BUCKET="your-bucket-name"
  $env:TEXTRACT_S3_PREFIX="textract"

IAM permissions required:
- textract:AnalyzeDocument
- textract:StartDocumentAnalysis
- textract:GetDocumentAnalysis
- s3:PutObject
- s3:GetObject

Notes:
- Images (.png/.jpg/.tif) use direct Textract call.
- PDFs are uploaded to S3 then processed by Textract.

---

4) Background templates + fonts
Templates:
- The PDF generator can draw a background image for each document type.
- Default lookup is from:
  backend/samples/output
  backend/samples/input

Override template directory:
  FAX_TEMPLATE_DIR=/path/to/your/templates

Supported filenames (per doc type):
  order_summary.(pdf|png|jpg|jpeg)
  packing_slip.(pdf|png|jpg|jpeg)
  delivery_note.(pdf|png|jpg|jpeg)
  delivery_detail.(pdf|png|jpg|jpeg)
  invoice.(pdf|png|jpg|jpeg)
  invoice_detail.(pdf|png|jpg|jpeg)
  invoice_statement.(pdf|png|jpg|jpeg)

Fonts (Japanese):
- Place font file at:
  backend/assets/fonts/NotoSansJP-Regular.otf
- Or set:
  FAX_JP_FONT_PATH=/path/to/font.otf

Notes:
- Image templates are supported for backgrounds.
- PDF background support can be added if needed.

---

5) Database persistence + audit
SQLite file:
  backend/data/fax.db

Key tables:
- salesorder
- orderline
- document
- product
- customer
- customerpricing
- purchaserecord
- productalias
- ocraudit (raw OCR text + meta)
- ocrauditline (parsed OCR rows)

Audit tables:
- Every upload stores raw OCR text and parsed fields.
- This guarantees traceability even if parsing changes later.

---

6) Local test flow (real OCR)
1) Start backend (uvicorn)
2) Login (admin / admin123)
3) Upload a PDF or image
4) Confirm OCR lines
5) Generate PDFs
6) Download PDFs

Verify DB:
  sqlite3 backend/data/fax.db
  .tables
  SELECT id, status FROM salesorder;
  SELECT order_id, normalized_name, quantity FROM orderline;
  SELECT order_id, document_type, file_path FROM document;
  SELECT order_id, length(raw_text) FROM ocraudit;

---

7) EC2 deployment (single instance)
1) Launch EC2 (Ubuntu 22.04)
2) Install deps:
   sudo apt update
   sudo apt install -y python3 python3-venv python3-pip git npm sqlite3
3) Clone repo
4) Build frontend:
   cd frontend && npm install && npm run build
5) Setup backend:
   cd backend && python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
6) Configure backend env:
   cp backend/.env.example backend/.env
   # fill AWS/Textract/admin/CORS values in backend/.env
7) Run backend:
   uvicorn app.main:app --host 0.0.0.0 --port 8000

Production hardening (systemd + restricted runtime):
- Deploy templates and scripts from `backend/deploy`.
- Install services:
  sudo bash /home/ubuntu/<repo>/backend/deploy/install-systemd.sh --app-dir /home/ubuntu/<repo> --user ubuntu
- Check status:
  sudo systemctl status fax-backend
  sudo systemctl status fax-backup.timer

SQLite backups (daily + manual):
- Daily timer: `fax-backup.timer` runs `backup.sh` and stores archives in `/var/backups/fax`.
- Customize retention/path in:
  /home/ubuntu/<repo>/backend/deploy/backup.env
- Manual backup:
  bash /home/ubuntu/<repo>/backend/deploy/backup.sh
- Manual restore (stop service first):
  sudo systemctl stop fax-backend
  bash /home/ubuntu/<repo>/backend/deploy/restore.sh /var/backups/fax/fax-backup-YYYYMMDDTHHMMSSZ.tar.gz /home/ubuntu/<repo>
  sudo systemctl start fax-backend

---

8) Troubleshooting
- 401 on download: token required unless endpoint is public.
- "Failed to fetch" from Vercel: HTTPS frontend cannot call HTTP backend.
- OCR errors: verify AWS region, IAM permissions, and S3 bucket.
- Garbled PDF text: install a JP font and set FAX_JP_FONT_PATH.
