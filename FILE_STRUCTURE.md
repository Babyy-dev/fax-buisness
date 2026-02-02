# Project File Structure & Responsibilities

This reference explains where the key functions, components, and assets live inside the `fax` repo.

## Root

| File/Folder | Description |
| --- | --- |
| `plan.md` | Project goals, scope, and current backend/AWS guidance. |
| `README.md` | Local workflow, AWS guidance, and notices about the `frontend`/`frontend-jp` builds. |
| `FILE_STRUCTURE.md` | This file. |

## Backend

| Path | Purpose |
| --- | --- |
| `backend/requirements.txt` | Python dependencies (FastAPI, SQLModel, uvicorn, multipart, aiofiles). |
| `backend/app/db.py` | SQLModel engine setup, `create_db_and_tables()`, and `get_session()` generator. `FAX_DB_URL` env var allows swapping SQLite for PostgreSQL/RDS. |
| `backend/app/models.py` | SQLModel tables for `Product`, `ProductAlias`, `Customer`, `CustomerPricing`, `SalesOrder`, `OrderLine`, and `PurchaseRecord`; each tracks timestamps for auditing. |
| `backend/app/schemas.py` | DTOs for uploads, extracted lines, customers, pricing, purchases, login/auth, order confirmation, documents, and PDF render requests/responses. |
| `backend/app/pdf_utils.py` | ReportLab helper that generates the final PDF outputs (order summary, packing slip, delivery note/detail, invoice/detail/statement). |
| `backend/app/main.py` | FastAPI app:
|  | • Startup seeds default products/customers via `seed_defaults()`. |
|  | • `POST /api/orders/upload` receives a fax, stores it in `backend/uploads/`, creates a `SalesOrder`, and seeds sample `OrderLine` rows. |
|  | • `GET /api/orders/{order_id}/lines` returns previously extracted lines for confirmation. |
|  | • Product, alias, customer, pricing, and purchase endpoints maintain masters and overrides. |
|  | • `POST /api/orders/{order_id}/confirm` finalizes line pricing/quantities. |
|  | • `POST /api/pdf/render` generates PDFs and stores them in `backend/generated/`. |
|  | • `/api/auth/login` issues a bearer token for the single-role login. |
|  | • Serves the built React frontend from `frontend/dist/` (root `/` + `/assets`). |

## Frontend (English)

| Path | Purpose |
| --- | --- |
| `frontend/package.json` | Vite project metadata (React + TypeScript) and scripts (`dev`, `build`, `preview`). |
| `frontend/.env.example` | Template showing `VITE_API_BASE_URL` for the API host. |
| `frontend/src/main.tsx` | Entry point: renders `<App />` inside `#root`. |
| `frontend/src/App.tsx` | React + TypeScript component:
|  | • `processSteps`, `pdfDeliverables`, and `nonFunctionalFocus` describe the workflow. |
|  | • Hooks fetch customers/products/aliases/pricing lines from FastAPI (`VITE_API_BASE_URL`). |
|  | • `handleUpload`, `handleAliasSubmit`, `handlePricingSubmit`, `handlePurchaseSubmit`, and `handlePdfRender` map to the corresponding API endpoints. |
|  | • Simple login form calls `/api/auth/login` and stores a bearer token. |
|  | • Layout includes hero, process grid, order intake panel (OCR table), product master, pricing/purchase forms, and PDF generation controls. |
|  | • Styles defined in `App.css` maintain the responsive card/grid layout; `index.css` defines fonts/background. |
| `frontend/src/App.css` | CSS for hero, stats, workflow panels, forms, tables, status chips, and responsive tweaks. |
| `frontend/src/index.css` | Global styles (Inter/Noto Sans JP fonts, radial background, root defaults). |

## Frontend (Japanese-only)

| Path | Purpose |
| --- | --- |
| `frontend-jp/` | Complete copy of `frontend/` that keeps the same React logic/API wiring. |
| `frontend-jp/.env.example` | Same environment hint for `VITE_API_BASE_URL`. |
| `frontend-jp/src/App.tsx` | Identical data flows/functions to the English build but with Japanese copywriting in the hero, steps, panels, buttons, and helper text, making it feel localized for the target users. |
| `frontend-jp/src/App.css` & `frontend-jp/src/index.css` | Mirrored styles; the layout is the same so both builds share the same CSS structure. |

## Dist / Build Artifacts

| Path | Purpose |
| --- | --- |
| `frontend/dist/` & `frontend-jp/dist/` | Production output from `npm run build`; copied to S3/CloudFront. |
| `backend/data/fax.db` | SQLite file generated at runtime (ignored but documented) used before migrating to PostgreSQL/RDS. |
| `backend/uploads/` | Stored fax PDFs awaiting OCR processing; the backend writes here on upload. |
| `backend/generated/` | Generated PDF outputs (order summary, packing slips, delivery notes, invoices). |

## Notes for Developers

- Use `VITE_API_BASE_URL` in either frontend before running `npm run dev` or `npm run build` so the UI can reach the FastAPI service. See `frontend` and `frontend-jp` readme notes for deployment.
- Backend seeds sample products/customers when tables are empty; the helper endpoints (`alias_suggestions`, health check) live inside `backend/app/main.py`.
- Keep `frontend-jp` in sync with English logic; the two directories share the same component structure but differ only in copy/style strings.
