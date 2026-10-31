import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import cv2
import numpy as np
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from rapidocr_onnxruntime import RapidOCR

app = FastAPI(title="PharmaCare RapidOCR service")
cv2.setNumThreads(1)
engine = RapidOCR()
TOKEN = os.getenv("RAPID_OCR_TOKEN", "").strip()
MAX_IMAGE_DIMENSION = 1600


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def root():
    return {"service": "pharmacare-rapidocr", "ok": True}


@app.post("/ocr")
async def ocr(file: UploadFile = File(...), x_ocr_token: str = Header(default="")):
    if not TOKEN or x_ocr_token != TOKEN:
        raise HTTPException(401, "Invalid OCR service token")
    data = await file.read()
    if len(data) > 4_000_000:
        raise HTTPException(413, "Image too large (max 4 MB)")
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(422, "Unreadable image")
    height, width = image.shape[:2]
    largest_dimension = max(height, width)
    if largest_dimension > MAX_IMAGE_DIMENSION:
        scale = MAX_IMAGE_DIMENSION / largest_dimension
        image = cv2.resize(
            image,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    try:
        result, _ = engine(image)
    except Exception as exc:
        raise HTTPException(502, "RapidOCR could not process this image") from exc
    result = result or []
    text = "\n".join(str(line[1]).strip() for line in result if len(line) > 1 and str(line[1]).strip())
    confidence = sum(float(line[2]) for line in result if len(line) > 2) / len(result) * 100 if result else 0
    return {"extracted_text": text, "confidence_score": round(confidence, 2)}
