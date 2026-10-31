# PharmaCare 2.0
Pharmacist-assisted dispensing and inventory. React + FastAPI + Postgres, deployable entirely on Vercel.

## Run locally (Python 3.12, Node 18+)
    python3.12 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
    pip install -r requirements.txt -r requirements-dev.txt
    python -m uvicorn app.main:app --reload --port 8000          # API (SQLite file)
    cd frontend && npm install && npm run dev                    # http://localhost:5173
On first open you see "Set up PharmaCare": create the first administrator, or click "Load demo data" (admin / Admin@123, pharmacist / Pharmacist@123).
Tests: `python -m pytest` (12 tests).

## Deploy on Vercel with Supabase PostgreSQL
1. In Supabase, open **Project Settings -> Database -> Connect** and copy the **Session pooler** URI. Use the pooler URI if the direct database host is not reachable from your network.
2. Push to GitHub and import the repository in Vercel (Framework: Other).
3. In Vercel **Settings -> Environment Variables**, add:
   - `DATABASE_URL`: the Supabase PostgreSQL URI
   - `JWT_SECRET`: a long random secret
   - `ADMIN_APPROVAL_CODE`: optional administrator approval secret
4. Enable the variables for **Production**, **Preview**, and **Development** as needed, then redeploy.
5. Open the deployed site and click **Load demo data**, or create the first administrator. The API health check is available at `/api/health`.

The backend already converts `postgresql://` and `postgres://` URLs for SQLAlchemy and creates the required tables on startup. Never commit the Supabase URI, database password, or JWT secret; keep them only in Vercel environment variables or an ignored local `.env` file.
Images live in the database (max 4 MB, the browser shrinks photos first). The Vercel deployment uses the lightweight image-processing dependencies and supports manual medicine entry. RapidOCR is optional for local deployments: install `requirements-ocr.txt` (included by `requirements-dev.txt`) to enable local OCR. If OCR is unavailable, the app says so and you can add medicines by hand.
OCR filters out non-medicine prescription text and suggests each medicine with its dosage, frequency, duration, and explicitly stated quantity for pharmacist review.
