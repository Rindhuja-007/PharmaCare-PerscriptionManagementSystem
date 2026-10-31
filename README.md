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
Images live in the database (max 4 MB, the browser shrinks photos first). The Vercel deployment uses lightweight dependencies and supports manual medicine entry. RapidOCR runs in the separate Render service described below; it remains optional for local deployments through `requirements-ocr.txt`.
OCR filters out non-medicine prescription text and suggests each medicine with its dosage, frequency, duration, and explicitly stated quantity for pharmacist review.

## Deploy RapidOCR on Render

The Vercel application can use RapidOCR through a separate Render web service. This keeps the large OCR dependencies and model files out of the Vercel function bundle.

1. Push this repository to GitHub.
2. In Render, choose **New + -> Blueprint**, select the repository, and apply the included `ocr_service/render.yaml`.
3. Wait for `pharmacare-rapidocr` to deploy. Open its `/health` URL and confirm it returns `{"ok":true}`.
4. In the Render service's environment variables, reveal the generated `RAPID_OCR_TOKEN` and copy it.
5. In Vercel, add these Production environment variables:
   - `RAPID_OCR_URL`: the Render service URL, without a trailing slash.
   - `RAPID_OCR_TOKEN`: the exact token copied from Render.
6. Redeploy Vercel, then open a prescription and click **Read prescription automatically**.

The Vercel backend sends the prescription image to the authenticated Render service. RapidOCR returns text and confidence; the existing extraction, catalogue matching, pharmacist verification, and dispensing workflow remains unchanged. Render's free service may sleep when idle, so the first OCR request can take longer.

If RapidOCR is unavailable or times out, the frontend automatically falls back to Tesseract.js in the browser. The browser fallback keeps the application usable without paid Render resources; only the recognized text is sent to Vercel. The first fallback use downloads the English OCR model and may take longer.
