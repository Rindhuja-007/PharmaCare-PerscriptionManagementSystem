import base64, io, json, os, re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from PIL import Image, ImageOps
from rapidfuzz import fuzz
from .db import Medicine, Batch, today
_ocr = None

class OCRServiceError(Exception):
    pass

GoogleVisionError = OCRServiceError

def _decode(data):
    import cv2
    import numpy as np
    im = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if im is None: raise ValueError("Unreadable image")
    return im
def preprocess(data):
    im = Image.open(io.BytesIO(data)).convert("L")
    if im.width > 1800:
        im.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
    im = ImageOps.autocontrast(im)
    im = im.point(lambda pixel: 255 if pixel > 160 else 0)
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()

def google_ocr(data):
    key = os.getenv("GOOGLE_VISION_API_KEY")
    if not key:
        raise GoogleVisionError("Google Vision is not configured on this server.")
    body = json.dumps({
        "requests": [{
            "image": {"content": base64.b64encode(data).decode("ascii")},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            "imageContext": {"languageHints": ["en-t-i0-handwrit"]},
        }]
    }).encode("utf-8")
    request = Request(
        "https://vision.googleapis.com/v1/images:annotate?key=" + key,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise GoogleVisionError(f"Google Vision request failed ({exc.code}).") from exc
    except (URLError, TimeoutError) as exc:
        raise GoogleVisionError("Google Vision could not be reached. Try again.") from exc
    error = (result.get("responses") or [{}])[0].get("error")
    if error:
        raise GoogleVisionError(error.get("message", "Google Vision rejected the image."))
    annotation = (result.get("responses") or [{}])[0].get("fullTextAnnotation") or {}
    text = annotation.get("text", "").strip()
    confidences = [
        float(symbol["confidence"])
        for page in annotation.get("pages", [])
        for block in page.get("blocks", [])
        for paragraph in block.get("paragraphs", [])
        for word in paragraph.get("words", [])
        for symbol in word.get("symbols", [])
        if symbol.get("confidence") is not None
    ]
    return text, (sum(confidences) / len(confidences) * 100 if confidences else 0)

def gemini_ocr(data):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise OCRServiceError("Gemini OCR is not configured on this server.")
    prompt = (
        "Transcribe this prescription image exactly as written. Return only the "
        "prescription text, one line per visible line. Preserve medicine names, "
        "dosages, frequencies, durations, and quantities. Do not invent or correct "
        "text, and do not include explanations or markdown."
    )
    body = json.dumps({
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {
                    "mime_type": "image/png",
                    "data": base64.b64encode(data).decode("ascii"),
                }},
            ]
        }],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "text/plain",
        },
    }).encode("utf-8")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    request = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise OCRServiceError(f"Gemini OCR request failed ({exc.code}).") from exc
    except (URLError, TimeoutError) as exc:
        raise OCRServiceError("Gemini OCR could not be reached. Try again.") from exc
    if result.get("error"):
        raise OCRServiceError(result["error"].get("message", "Gemini rejected the image."))
    candidates = result.get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts", []) if candidates else []
    text = "\n".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise OCRServiceError("Gemini returned no readable text for this image.")
    return text, 0

def ocr(data):
    if os.getenv("GEMINI_API_KEY"):
        return gemini_ocr(data)
    if os.getenv("GOOGLE_VISION_API_KEY"):
        return google_ocr(data)
    global _ocr
    if _ocr is None:
        import cv2
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
        _ocr = RapidOCR()
    res, _ = _ocr(_decode(data)); res = res or []
    return "\n".join(r[1] for r in res), (sum(float(r[2]) for r in res) / len(res) * 100 if res else 0)
RE_BLOCK = re.compile(r"\b(dr\.?|md|mbbs|dnb|frcs|consultant|reg\.? ?no|plot|colony|road|street|sector|floor|hospital|clinic|tele(phone)?|mobile|email|website|age|yrs?|gender|weight|bp|pulse|temp|dm|htn|hypertension|diabetes|diagnosis|c/o|o/e|review after|hyderabad|bangalore|chennai|mumbai|delhi)\b|\d{6}", re.I)
RE_UI_CAPTURE = re.compile(r"\b(pharmacare|dashboard|prescriptions|medicines detected|catalogue matches|medicine to dispense|quantity \(units\)|verify|reject|save verification|same ingredient|in stock|to dispense)\b", re.I)
FIXES = {
    "si zodon plua5": "Sizodon Plus",
    "si zodon plus": "Sizodon Plus",
    "s' zodon plus": "Sizodon Plus",
    "qybpir": "Qutipin",
    "qukpin9omy": "Qutipin",
    "qukpin9obmy": "Qutipin 200 mg",
    "qukpin 20omg": "Qutipin 200 mg",
    "qutspin 90bmg": "Qutipin 200 mg",
    "arivanclor&pm)": "Ativan 2 mg",
    "ari van (lor&pem)": "Ativan",
    "rivobil": "Rivotril 0.5 mg",
    "rivolbil o.smg <clomegpcm)": "Rivotril 0.5 mg",
    "serta o": "Serta 50 mg",
    "clor*gpm)": "(Lorazepam)",
    "ri vo(i1": "Rivotril",
}
RE_FORM = re.compile(r"^\s*(?:\d{1,2}[.)]\s*)?(tab(?:let)?|cap(?:sule)?|inj(?:ection)?|syp|syrup|drops?|oint(?:ment)?)\b\.?\s*(.*)", re.I)
RE_STR = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|%)\b", re.I)
RE_MED_HINT = re.compile(r"\b(?:tab(?:let)?|cap(?:sule)?|inj(?:ection)?|syp|syrup|drops?|oint(?:ment)?)\b|"
                         r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|%)\b", re.I)
RE_FREQ = re.compile(r"\b(od|bd|tid|qid|hs|prn|\d\s*-\s*\d\s*-\s*\d|morning|night)\b", re.I)
RE_DUR = re.compile(r"(\d+)\s*(days?|weeks?|months?)", re.I)
RE_QTY = re.compile(
    r"(?:\b(?:qty|quantity|nos?|no)\s*[:.]?\s*|#\s*)(\d+)\s*(?:tabs?|tablets?|caps?|capsules?|units?|strips?|bottles?|packs?)?\b"
    r"|[x×]\s*(\d+)\s*(?=(?:tabs?|tablets?|caps?|capsules?|units?|strips?|bottles?|packs?)\b|$)"
    r"|\b(\d+)\s*(?:tabs?|tablets?|caps?|capsules?|units?|strips?|bottles?|packs?)\b",
    re.I,
)
def _fix_key(value):
    value = re.sub(r"^\d+[.)]\s*", "", value.strip().lower())
    return re.sub(r"\s+", " ", value)
def extract(text, medicine_names=None):
    out, pending = [], None
    medicine_names = medicine_names or []
    ui_capture = bool(RE_UI_CAPTURE.search(text))
    lines = [l.strip() for l in text.splitlines()]
    for index, ln in enumerate(lines):
        if not ln: continue
        schedule_only = (RE_FREQ.search(ln) or RE_DUR.search(ln)) and not RE_MED_HINT.search(ln)
        dosage_only = RE_STR.fullmatch(ln) and not RE_FORM.match(ln)
        if out and (schedule_only or dosage_only):
            continuation = ln
            s, f, d, q = RE_STR.search(continuation), RE_FREQ.search(continuation), RE_DUR.search(continuation), RE_QTY.search(continuation)
            current = out[-1]
            if s: current["dosage"] = s.group(0)
            if f: current["frequency"] = f.group(0)
            if d: current["duration"] = d.group(0)
            if q: current["quantity"] = next((int(x) for x in q.groups() if x), None)
            if current["quantity"] is None:
                current["quantity"] = _course_quantity(current["frequency"], current["duration"])
            continue
        m = RE_FORM.match(ln)
        catalogue_name = None
        normalized = FIXES.get(_fix_key(ln))
        if not ui_capture and not m and not normalized and medicine_names and len(ln) <= 100:
            candidate = max(medicine_names, key=lambda n: fuzz.WRatio(ln.lower(), n.lower()))
            if fuzz.WRatio(ln.lower(), candidate.lower()) >= 72:
                catalogue_name = candidate
        if RE_BLOCK.search(ln) and not m and not RE_MED_HINT.search(ln) and not catalogue_name and ln.lower() not in FIXES: continue
        if m:
            body = m.group(2).strip()
        elif catalogue_name:
            body = catalogue_name
        elif RE_MED_HINT.search(ln):
            body = ln
        else:
            if not normalized: continue
            body = normalized
        body = FIXES.get(_fix_key(body), body)
        s, f, d, q = RE_STR.search(body), RE_FREQ.search(body), RE_DUR.search(body), RE_QTY.search(body)
        name = re.sub(
            r"(?:\s+|^)[x×]\s*$",
            "",
            RE_QTY.sub("", RE_DUR.sub("", RE_FREQ.sub("", RE_STR.sub("", body)))),
            flags=re.I,
        ).strip(" -.,")
        name = re.sub(r"\b(?:tab(?:let)?|cap(?:sule)?|inj(?:ection)?|syp|syrup|drops?|oint(?:ment)?)\b\.?", "", name, flags=re.I).strip(" -.,")
        if len(re.sub(r"[^A-Za-z]", "", name)) >= 2:
            quantity = next((int(x) for x in q.groups() if x), None) if q else None
            if quantity is None:
                quantity = _course_quantity(f.group(0) if f else None, d.group(0) if d else None)
            out.append(dict(
                name=name,
                dosage=s.group(0) if s else None,
                frequency=f.group(0) if f else None,
                duration=d.group(0) if d else None,
                quantity=quantity,
            ))
    return out

def parse(text, medicines=None):
    items = extract(text)
    return [dict(item, line=item["name"]) for item in items]

def _course_quantity(frequency, duration):
    if not frequency or not duration: return None
    schedule = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*", frequency)
    per_day = sum(int(x) for x in schedule.groups()) if schedule else {
        "OD": 1, "BD": 2, "TID": 3, "QID": 4, "HS": 1
    }.get(frequency.upper())
    span = re.fullmatch(r"\s*(\d+)\s*(day|days|week|weeks|month|months)\s*", duration, re.I)
    if not per_day or not span: return None
    units = int(span.group(1)) * {"day": 1, "days": 1, "week": 7, "weeks": 7, "month": 30, "months": 30}[span.group(2).lower()]
    return per_day * units
STOP = {"tablet", "capsule", "syrup", "plus", "oral", "dose", "tab", "cap"}
def tokens(m):
    t = re.findall(r"[a-z]{4,}", f"{m.generic_name or ''} {m.composition or ''}".lower())
    return {x for x in t if x not in STOP and x not in {"mg", "mcg"}}
def usable(db, mid, lock=False):
    q = db.query(Batch).filter(Batch.medicine_id == mid, Batch.quantity > 0, Batch.expiry_date >= today()).order_by(Batch.expiry_date, Batch.id)
    return q.with_for_update().all() if lock else q.all()
def stock(db, mid): return sum(b.quantity for b in usable(db, mid))
def match(db, name, dosage=None):
    meds = db.query(Medicine).all(); scored = []
    for m in meds:
        sc = max(fuzz.WRatio(name.lower(), (x or "").lower()) for x in [m.medicine_name, m.brand_name, m.generic_name, m.composition])
        scored.append((sc, m))
    scored.sort(key=lambda x: -x[0]); cands = []
    for sc, m in scored[:5]:
        cands.append(dict(medicine_id=m.id, name=m.medicine_name, score=round(sc, 1), level="HIGH" if sc >= 90 else "MEDIUM" if sc >= 70 else "LOW", stock=stock(db, m.id)))
    subs = []
    if scored and scored[0][0] >= 70:
        top = scored[0][1]; tk = tokens(top)
        for m in meds:
            if m.id != top.id and tk and tk & tokens(m):
                s = stock(db, m.id); subs.append(dict(medicine_id=m.id, name=m.medicine_name, stock=s, is_available=s > 0))
        subs.sort(key=lambda x: (not x["is_available"], -x["stock"]))
    return cands, subs
