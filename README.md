# Fax Order Automation – Frontend

## Purpose
The React + TypeScript frontend is the user entry point for the fax-order automation MVP. It mirrors the workflow described in `plan.md` (order intake, product/customer masters, pricing overrides, and PDF outputs) and targets 1–3 internal desktop users who confirm OCR data before saving orders.

## Local workflow
- `npm install` (run once) to populate `node_modules`.
- `npm run dev` starts Vite in development mode with HMR on `http://localhost:5173`.
- `npm run build` compiles TypeScript, bundles the app, and drops static assets into `frontend/dist`.
- `npm run preview` serves the production bundle locally after running the build.
- Set `VITE_API_BASE_URL` (see `frontend/.env.example`) to the FastAPI host before running dev or build so the UI can reach `/api/*`.

## Localized frontends
- `frontend/`: English-centric experience that we use for documentation, QA, and AWS builds.
- `frontend-jp/`: Japanese-only copy with localized copywriting; build it exactly the same (install, set `VITE_API_BASE_URL`, then `npm run build`) when you need a Japanese-hosted SPA.

## AWS deployment guidance
1. **S3 + CloudFront**  
   - `npm run build`, then sync `frontend/dist` to an S3 bucket configured for static website hosting (or use the bucket as the CloudFront origin).  
   - Apply IAM policies limiting uploads, then configure CloudFront for HTTPS + caching and point the DNS record to the distribution.  
   - Invalidation can be scripted (`aws cloudfront create-invalidation ...`), or use versioned object keys for fast rollouts.
2. **AWS Amplify Console (alternative)**  
   - Connect the repo to Amplify or push the `frontend` directory via the Amplify CLI.  
   - Configure the build settings to run `npm install` and `npm run build`, then let Amplify publish each successful merge.  
   - Use Amplify Environment Variables to provide API base URLs once the FastAPI backend on AWS (e.g., ECS/ECSFargate or Lambda behind API Gateway) is available.
   - Ensure the API returns `preview_url` values that point at the S3 bucket serving generated PDFs so clicks from the React UI open the correct document.

## Next actions
- Wire API endpoints for file uploads, OCR previews, and PDF downloads.
- Add environment-aware configs (e.g., `VITE_API_BASE_URL`) before deploying.

## Backend (Python + FastAPI)
- Run `python -m pip install -r backend/requirements.txt` before starting.
- Launch the API with `uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000`; it serves the `/api/*` routes documented in `backend/app/main.py`.
- Uploaded fax PDFs land in `backend/uploads/` and are linked to `SalesOrder` rows; extracted rows, product/customer masters, pricing overrides, and purchase records all persist in `backend/data/fax.db` via SQLModel (seed data is created automatically at startup).
- The upload endpoint accepts PDFs and common image formats (`.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`) for FAX input.
- Default login is `admin` / `admin123` (override with `FAX_ADMIN_USER` and `FAX_ADMIN_PASSWORD`).
- If you change models, delete `backend/data/fax.db` to recreate the schema (SQLite has no migrations yet).
- The backend can serve the frontend build directly: run `npm run build` in `frontend/` and then open `http://localhost:8000/` (assets are served from `/assets`).
- Key endpoints:
  1. `POST /api/orders/upload` (multipart upload + optional `customer_id` form field) creates a staging order and sample OCR lines.
  2. `GET /api/orders/{order_id}/lines`, `POST /api/products/aliases`, `POST /api/customers/{customer_id}/pricing`, and `POST /api/purchases` cover the workflow from OCR confirmation through pricing/purchase capture.
  3. `POST /api/orders/{order_id}/confirm` updates line pricing/aliases and locks the order.
  4. `POST /api/pdf/render` generates one of the final PDFs and returns a local download URL (`/api/documents/{id}/download`).
  - To use PostgreSQL (e.g., RDS) instead of SQLite, follow the `backend/POSTGRES.md` instructions and point `FAX_DB_URL` at your Postgres connection string (requires `psycopg[binary]` from the requirements file).

## Infrastructure notes
- The current SQLite file (`backend/data/fax.db`) is ready to swap to PostgreSQL/RDS later; `backend/app/db.py` reads `FAX_DB_URL` from the environment so you can point it to `postgresql://...` without code changes.
- Persisted PDFs could be pushed to an S3 bucket (use the same bucket for `PDF preview` URLs) and the API deployed via ECS/Fargate, App Runner, or Lambda+API Gateway behind the React frontend hosted on S3/CloudFront or Amplify.
