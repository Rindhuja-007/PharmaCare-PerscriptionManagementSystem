# PharmaCare 2.0
Pharmacist-assisted dispensing and inventory. React + FastAPI + Postgres, deployable entirely on Vercel.

## Run locally (Python 3.12, Node 18+)
    python3.12 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
    pip install -r requirements.txt -r requirements-dev.txt
    python -m uvicorn app.main:app --reload --port 8000          # API (SQLite file)
    cd frontend && npm install && npm run dev                    # http://localhost:5173
On first open you see "Set up PharmaCare": create the first administrator, or click "Load demo data" (admin / Admin@123, pharmacist / Pharmacist@123).
Tests: `python -m pytest` (12 tests).

## Deploy on Vercel
1. Push to GitHub, import the repo in Vercel (Framework: Other).
2. Storage -> add Neon Postgres (sets DATABASE_URL).
3. Settings -> Environment Variables: JWT_SECRET (long random string), optional ADMIN_APPROVAL_CODE.
4. Deploy. API docs at /api/docs.
Images live in the database (max 4 MB, the browser shrinks photos first). OCR uses RapidOCR; if it is unavailable the app says so and you can add medicines by hand.
OCR filters out non-medicine prescription text and suggests each medicine with its dosage, frequency, duration, and explicitly stated quantity for pharmacist review.
