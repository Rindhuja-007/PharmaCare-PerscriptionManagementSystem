from fastapi import FastAPI
from app.main import app as inner
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/api", inner)  # Vercel keeps the /api prefix; docs are at /api/docs
