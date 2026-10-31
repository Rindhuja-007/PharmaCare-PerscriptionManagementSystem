import os, io, csv, uuid, secrets, datetime as dt
from decimal import Decimal
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from . import services as S
from .db import *
from .security import *
app = FastAPI(title="PharmaCare")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
Base.metadata.create_all(engine)
D = Depends(get_db); U = Depends(current_user)
def row(o): return {c.name: (float(getattr(o, c.name)) if isinstance(getattr(o, c.name), Decimal) else getattr(o, c.name)) for c in o.__table__.columns if c.name not in ("password_hash", "image_data", "processed_data")}
@app.get("/health")
def health(): return {"ok": True}
# ---------- auth ----------
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
class Reg(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    email: str = Field(pattern=EMAIL, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    approval_code: Optional[str] = None
class StaffNew(Reg): role: str = "PHARMACIST"
class Login(BaseModel): username: str; password: str
class PwChange(BaseModel): current_password: str; new_password: str = Field(min_length=8, max_length=128)
def _login(db, un, pw):
    u = db.query(User).filter_by(username=(un or "").strip().lower()).first()
    if not u or not verify_password(pw, u.password_hash): raise HTTPException(401, "Incorrect username or password")
    if not u.is_active: raise HTTPException(403, "This account has been deactivated. Contact an administrator.")
    if not u.is_approved: raise HTTPException(403, "Your account is waiting for administrator approval.")
    return {"access_token": create_token(u.id), "token_type": "bearer", "user": row(u)}
def _admins(db): return db.query(User).filter_by(role="ADMIN", is_approved=True, is_active=True).count()
def _create(db, b, role, approved, by=None):
    if db.query(User).filter((User.username == b.username.lower()) | (User.email == b.email.lower())).first(): raise HTTPException(409, "That username or email is already registered")
    u = User(name=b.name.strip(), username=b.username.lower(), email=b.email.lower(), password_hash=hash_password(b.password), role=role, is_approved=approved, approved_by=by)
    db.add(u); db.commit(); return u
@app.get("/auth/status")
def status(db=D):
    c = lambda **k: db.query(User).filter_by(**k).count(); a = _admins(db)
    return dict(admin_count=a, staff_count=c(role="PHARMACIST", is_approved=True), initial_setup_required=a == 0, pending_admin_count=c(is_approved=False))
@app.post("/auth/register-admin")
def register_admin(b: Reg, db=D):
    first = _admins(db) == 0
    ok = first or secrets.compare_digest((b.approval_code or "").encode(), ADMIN_CODE.encode())
    _create(db, b, "ADMIN", ok)
    msg = "Administrator account created." if ok else "Request sent. An existing administrator must approve it before you can sign in."
    return JSONResponse({"approved": ok, "detail": msg}, status_code=201 if ok else 202)
@app.post("/auth/register")
def register(b: Reg, db=D):
    if _admins(db) == 0: raise HTTPException(409, "Set up the first administrator account before requesting access")
    _create(db, b, "PHARMACIST", False)
    return JSONResponse({"approved": False, "detail": "Request sent. An administrator must approve your account before you can sign in."}, status_code=202)
@app.post("/auth/login")
def login(b: Login, db=D): return _login(db, b.username, b.password)
@app.post("/auth/token")
def token(f: OAuth2PasswordRequestForm = Depends(), db=D): return _login(db, f.username, f.password)
@app.get("/auth/me")
def me(u=U): return row(u)
@app.post("/auth/change-password")
def change_pw(b: PwChange, db=D, u=U):
    if not verify_password(b.current_password, u.password_hash): raise HTTPException(400, "Current password is incorrect")
    u.password_hash = hash_password(b.new_password); audit(db, u.id, "PASSWORD_CHANGED", "User", u.id, u.username); db.commit(); return {"ok": True}
@app.get("/auth/staff")
def staff(db=D, a=Depends(admin_only)): return [row(u) for u in db.query(User).order_by(User.id)]
@app.post("/auth/staff", status_code=201)
def add_staff(b: StaffNew, db=D, a=Depends(admin_only)):
    if b.role not in ("ADMIN", "PHARMACIST"): raise HTTPException(422, "Role must be ADMIN or PHARMACIST")
    u = _create(db, b, b.role, True, a.id); audit(db, a.id, "STAFF_CREATED", "User", u.id, u.username); db.commit(); return row(u)
@app.post("/auth/approve-admin/{uid}")
def approve(uid: int, db=D, a=Depends(admin_only)):
    u = db.get(User, uid)
    if not u: raise HTTPException(404, "User not found")
    u.is_approved = True; u.approved_by = a.id; audit(db, a.id, "USER_APPROVED", "User", uid, u.username); db.commit(); return row(u)
@app.post("/auth/reject-admin/{uid}")
def reject(uid: int, db=D, a=Depends(admin_only)):
    u = db.get(User, uid)
    if not u or u.is_approved: raise HTTPException(404, "No pending request with that id")
    audit(db, a.id, "USER_REJECTED", "User", uid, u.username); db.delete(u); db.commit(); return {"ok": True}
@app.delete("/auth/staff/{uid}")
def deactivate(uid: int, db=D, a=Depends(admin_only)):
    u = db.get(User, uid)
    if not u: raise HTTPException(404, "User not found")
    if u.id == a.id: raise HTTPException(400, "You cannot deactivate your own account")
    if u.role == "ADMIN" and _admins(db) <= 1: raise HTTPException(400, "At least one active administrator is required")
    u.is_active = False; audit(db, a.id, "USER_DEACTIVATED", "User", uid, u.username); db.commit(); return {"ok": True}
@app.post("/auth/staff/{uid}/activate")
def activate(uid: int, db=D, a=Depends(admin_only)):
    u = db.get(User, uid)
    if not u: raise HTTPException(404, "User not found")
    u.is_active = True; audit(db, a.id, "USER_ACTIVATED", "User", uid, u.username); db.commit(); return row(u)
CATALOG = [("Crocin 500", "Paracetamol", "500 mg", "Tablet", "Analgesic", "Rack A-01", 20, 2.5, []),
 ("Dolo 650", "Paracetamol", "650 mg", "Tablet", "Analgesic", "Rack A-01", 30, 3.0, [("DL-2401", 120, 400, 1.2, 2.1), ("DL-2312", 30, 45, 1.1, 2.0)]),
 ("Metformin 500", "Metformin", "500 mg", "Tablet", "Antidiabetic", "Rack B-02", 30, 1.5, [("MF-77", 24, 300, 0.6, 1.1)]),
 ("Amoxicillin 500", "Amoxicillin", "500 mg", "Capsule", "Antibiotic", "Rack C-03", 25, 5.0, [("AX-10", 200, 500, 1.8, 3.2)]),
 ("Azithromycin 500", "Azithromycin", "500 mg", "Tablet", "Antibiotic", "Rack C-04", 15, 22.0, [("AZ-5", 60, 250, 8, 14)]),
 ("Pantoprazole 40", "Pantoprazole", "40 mg", "Tablet", "Antacid", "Rack D-01", 30, 6.0, [("PN-9", 90, 330, 2, 3.5)]),
 ("Cetirizine 10", "Cetirizine", "10 mg", "Tablet", "Antihistamine", "Rack D-02", 25, 1.2, [("CT-3", 15, 20, 0.3, 0.8)]),
 ("Atorvastatin 10", "Atorvastatin", "10 mg", "Tablet", "Statin", "Rack B-05", 20, 7.0, [("AT-8", 150, 600, 1.5, 2.6)])]
@app.post("/auth/seed-demo")
def seed(db=D):
    if db.query(User).count(): raise HTTPException(409, "Demo data can only be loaded into an empty system")
    for n, p, r in (("admin", "Admin@123", "ADMIN"), ("pharmacist", "Pharmacist@123", "PHARMACIST")):
        db.add(User(name=n.title(), username=n, email=f"{n}@demo.local", password_hash=hash_password(p), role=r))
    sup = Supplier(name="MediSource Distributors", contact="+91 90000 00000"); db.add(sup); db.flush()
    for n, g, st, form, cat, rack, ro, mrp, bs in CATALOG:
        m = Medicine(medicine_name=n, generic_name=g, composition=f"{g} ({st.replace(' ', '')})", strength=st, dosage_form=form, category=cat, rack_location=rack, reorder_level=ro, mrp=mrp); db.add(m); db.flush()
        for bn, q, days, buy, sell in bs: db.add(Batch(medicine_id=m.id, batch_number=bn, quantity=q, expiry_date=today() + dt.timedelta(days=days), purchase_price=buy, selling_price=sell, supplier_id=sup.id))
    db.flush(); refresh_alerts(db); db.commit(); return {"ok": True}
# ---------- medicines / inventory ----------
class Med(BaseModel):
    medicine_name: str; generic_name: Optional[str] = None; composition: Optional[str] = None; brand_name: Optional[str] = None
    strength: Optional[str] = None; dosage_form: Optional[str] = None; rack_location: Optional[str] = None; shelf_number: Optional[str] = None
    reorder_level: int = 15; mrp: Optional[float] = None; prescription_required: bool = True; category: Optional[str] = None; manufacturer: Optional[str] = None; storage_condition: Optional[str] = None
@app.get("/medicines")
def meds(search: str = "", db=D, u=U):
    q = db.query(Medicine)
    if search: q = q.filter(Medicine.medicine_name.ilike(f"%{search}%") | Medicine.generic_name.ilike(f"%{search}%"))
    return [{**row(m), "usable_stock": S.stock(db, m.id)} for m in q.limit(200)]
@app.post("/medicines", status_code=201)
def add_med(b: Med, db=D, u=U):
    if db.query(Medicine).filter(func.lower(Medicine.medicine_name) == b.medicine_name.strip().lower()).first(): raise HTTPException(409, "A medicine with this name already exists")
    m = Medicine(**b.model_dump()); db.add(m); db.flush(); audit(db, u.id, "MEDICINE_CREATED", "Medicine", m.id, m.medicine_name)
    refresh_alerts(db); db.commit(); return row(m)
@app.delete("/medicines/{mid}")
def del_med(mid: int, db=D, a=Depends(admin_only)):
    if db.query(Batch).filter_by(medicine_id=mid).first() or db.query(TransactionItem).filter_by(medicine_id=mid).first(): raise HTTPException(409, "Medicine has stock or history")
    db.query(Alert).filter_by(medicine_id=mid).delete(); db.query(Medicine).filter_by(id=mid).delete(); db.commit(); return {"ok": True}
class Stock(BaseModel): medicine_id: int; batch_number: str; quantity: int; expiry_date: dt.date; purchase_price: float; selling_price: float
@app.post("/inventory/stock", status_code=201)
def add_stock(b: Stock, db=D, u=U):
    if b.quantity <= 0: raise HTTPException(422, "Quantity must be positive")
    if not db.get(Medicine, b.medicine_id): raise HTTPException(404, "Medicine not found")
    if b.purchase_price < 0 or b.selling_price < 0: raise HTTPException(422, "Prices cannot be negative")
    x = Batch(**b.model_dump()); db.add(x); db.flush(); audit(db, u.id, "STOCK_ADDED", "Batch", x.id, f"{b.quantity} units"); refresh_alerts(db); db.commit(); return row(x)
@app.get("/inventory")
def inv(db=D, u=U): return [{**row(b), "medicine": b.medicine.medicine_name, "expired": b.expiry_date < today()} for b in db.query(Batch).order_by(Batch.expiry_date)]
def refresh_alerts(db):
    read = {(a.alert_type, a.medicine_id, a.batch_id) for a in db.query(Alert).filter_by(is_read=True)}
    db.query(Alert).delete()
    for m in db.query(Medicine):
        s = S.stock(db, m.id)
        if s == 0: db.add(Alert(alert_type="OUT_OF_STOCK", medicine_id=m.id, message=f"{m.medicine_name} has no usable stock", severity="CRITICAL"))
        elif s <= m.reorder_level: db.add(Alert(alert_type="LOW_STOCK", medicine_id=m.id, message=f"{m.medicine_name}: {s} left", severity="WARNING"))
        for b in m.batches:
            if b.quantity <= 0: continue
            if b.expiry_date < today(): db.add(Alert(alert_type="EXPIRED", medicine_id=m.id, batch_id=b.id, message=f"{m.medicine_name} batch {b.batch_number} expired", severity="CRITICAL"))
            elif b.expiry_date <= today() + dt.timedelta(days=90): db.add(Alert(alert_type="EXPIRING_SOON", medicine_id=m.id, batch_id=b.id, message=f"{m.medicine_name} batch {b.batch_number} expires {b.expiry_date}", severity="WARNING"))
    db.flush()
    for a in db.query(Alert): a.is_read = (a.alert_type, a.medicine_id, a.batch_id) in read
@app.post("/alerts/refresh")
def alerts_refresh(db=D, u=U): refresh_alerts(db); db.commit(); return {"ok": True}
@app.get("/alerts")
def alerts(unread_only: bool = False, db=D, u=U):
    q = db.query(Alert); q = q.filter_by(is_read=False) if unread_only else q
    return [row(a) for a in q.order_by(Alert.id.desc())]
@app.put("/alerts/{aid}/read")
def read_alert(aid: int, db=D, u=U): db.query(Alert).filter_by(id=aid).update({"is_read": True}); db.commit(); return {"ok": True}
@app.get("/reports/dashboard")
def dash(db=D, u=U):
    t0 = dt.datetime.combine(today(), dt.time.min, dt.timezone.utc)
    return dict(pending_review=db.query(Prescription).filter(Prescription.status.in_(["UPLOADED", "PROCESSED"])).count(), ready_to_dispense=db.query(Prescription).filter_by(status="VERIFIED").count(), unread_alerts=db.query(Alert).filter_by(is_read=False).count(), total_units=db.query(func.coalesce(func.sum(Batch.quantity), 0)).scalar(),
        expiring_batches=db.query(Batch).filter(Batch.quantity > 0, Batch.expiry_date <= today() + dt.timedelta(days=90)).count(),
        out_of_stock=sum(1 for m in db.query(Medicine) if S.stock(db, m.id) == 0),
        todays_sales=float(db.query(func.coalesce(func.sum(Transaction.total_amount), 0)).filter(Transaction.created_at >= t0).scalar()))
# ---------- prescriptions ----------
def rx(db, pid):
    p = db.get(Prescription, pid)
    if not p: raise HTTPException(404, "Prescription not found")
    return p
def rx_out(p): return {**row(p), "items": [row(i) for i in p.items]}
@app.post("/prescriptions/upload", status_code=201)
def upload(file: UploadFile = File(...), patient_reference: str = Form(None), doctor_name: str = Form(None), db=D, u=U):
    data = file.file.read()
    if len(data) > 4_000_000: raise HTTPException(413, "Image too large (max 4 MB)")
    if data[:3] != b"\xff\xd8\xff" and data[:4] != b"\x89PNG": raise HTTPException(422, "JPG or PNG only")
    p = Prescription(prescription_number="RX-" + uuid.uuid4().hex[:12].upper(), patient_reference=patient_reference, doctor_name=doctor_name, image_path="db", image_data=data, created_by=u.id)
    db.add(p); db.flush(); audit(db, u.id, "PRESCRIPTION_UPLOADED", "Prescription", p.id, p.prescription_number); db.commit(); return rx_out(p)
@app.get("/prescriptions")
def rx_list(db=D, u=U): return [{**row(p), "item_count": len(p.items)} for p in db.query(Prescription).order_by(Prescription.id.desc())]
@app.get("/prescriptions/{pid}")
def rx_get(pid: int, db=D, u=U): return rx_out(rx(db, pid))
@app.post("/prescriptions/{pid}/preprocess")
def rx_pre(pid: int, db=D, u=U):
    p = rx(db, pid)
    try: p.processed_data = S.preprocess(p.image_data)
    except ValueError as e: raise HTTPException(422, str(e))
    p.processed_image_path = "db"; db.commit(); return {"processed_image_path": "db"}
@app.post("/prescriptions/{pid}/process")
def rx_ocr(pid: int, db=D, u=U):
    p = rx(db, pid)
    try: txt, conf = S.ocr(p.processed_data or p.image_data)
    except S.OCRServiceError as e: raise HTTPException(502, str(e))
    except ImportError: raise HTTPException(503, "The OCR engine is not available on this server. Add the medicines manually instead.")
    except ValueError as e: raise HTTPException(422, str(e))
    p.extracted_text, p.confidence_score = txt, round(conf, 2)
    if p.status == "UPLOADED": p.status = "PROCESSED"
    db.commit(); return {"extracted_text": txt, "confidence_score": p.confidence_score}  # never approves, never touches stock
class OCRText(BaseModel):
    extracted_text: str = Field(min_length=1, max_length=100_000)
    confidence_score: Optional[float] = Field(default=0, ge=0, le=100)
@app.post("/prescriptions/{pid}/process-text")
def rx_text(pid: int, b: OCRText, db=D, u=U):
    p = rx(db, pid)
    p.extracted_text = b.extracted_text.strip()
    p.confidence_score = round(b.confidence_score or 0, 2)
    if p.status == "UPLOADED": p.status = "PROCESSED"
    db.commit(); return {"extracted_text": p.extracted_text, "confidence_score": p.confidence_score}
@app.post("/prescriptions/{pid}/extract")
def rx_extract(pid: int, db=D, u=U):
    p = rx(db, pid)
    if not p.extracted_text: raise HTTPException(409, "Run OCR first")
    if p.status in ("VERIFIED", "DISPENSED"): raise HTTPException(409, "Already finalised")
    p.items.clear()
    names = [m.medicine_name for m in db.query(Medicine).all()]
    for e in S.extract(p.extracted_text, names): p.items.append(PrescriptionItem(extracted_medicine_name=e["name"], dosage=e["dosage"], frequency=e["frequency"], duration=e["duration"], quantity=e["quantity"]))
    db.commit(); return [row(i) for i in p.items]
@app.post("/prescriptions/{pid}/match")
def rx_match(pid: int, db=D, u=U):
    p = rx(db, pid); res = []
    for i in p.items:
        c, subs = S.match(db, i.extracted_medicine_name)
        if c and c[0]["score"] >= 80: i.matched_medicine_name, i.confidence_score = c[0]["name"], c[0]["score"]
        res.append(dict(item_id=i.id, candidates=c, substitutes=subs))
    db.commit(); return res
class NewItem(BaseModel): quantity: Optional[int] = None; extracted_medicine_name: str; dosage: Optional[str] = None; frequency: Optional[str] = None; duration: Optional[str] = None; medicine_id: Optional[int] = None
@app.post("/prescriptions/{pid}/items", status_code=201)
def rx_add(pid: int, b: NewItem, db=D, u=U):
    p = rx(db, pid)
    if p.status == "DISPENSED": raise HTTPException(409, "Already dispensed")
    i = PrescriptionItem(**b.model_dump()); p.items.append(i)
    if p.status in ("VERIFIED", "REJECTED"): p.status = "PROCESSED"
    db.commit(); return row(i)
class Dec(BaseModel): item_id: int; verification_status: str; medicine_id: Optional[int] = None; quantity: Optional[int] = None; dosage: Optional[str] = None; frequency: Optional[str] = None; duration: Optional[str] = None
class Verify(BaseModel): items: List[Dec]
@app.put("/prescriptions/{pid}/verify")
def rx_verify(pid: int, b: Verify, db=D, u=U):
    p = rx(db, pid)
    if p.status == "DISPENSED": raise HTTPException(409, "Already dispensed")
    ids = {i.id: i for i in p.items}
    if {d.item_id for d in b.items} != set(ids): raise HTTPException(422, "A decision is required for every line item")
    for d in b.items:
        if d.verification_status not in ("VERIFIED", "REJECTED"): raise HTTPException(422, "Status must be VERIFIED or REJECTED")
        if d.verification_status == "VERIFIED" and (not d.quantity or d.quantity <= 0 or not d.medicine_id or not db.get(Medicine, d.medicine_id)):
            raise HTTPException(422, "Verified items need a catalogue medicine and quantity > 0")
    for d in b.items:
        i = ids[d.item_id]; i.verification_status = d.verification_status
        if d.verification_status == "VERIFIED": i.medicine_id, i.quantity = d.medicine_id, d.quantity
        for k in ("dosage", "frequency", "duration"):
            if getattr(d, k) is not None: setattr(i, k, getattr(d, k))
    ok = any(i.verification_status == "VERIFIED" for i in p.items)
    p.status = "VERIFIED" if ok else "REJECTED"; p.verified_by = u.id; p.verified_at = dt.datetime.now()
    audit(db, u.id, "PRESCRIPTION_VERIFIED" if ok else "PRESCRIPTION_REJECTED", "Prescription", p.id, p.prescription_number); db.commit(); return rx_out(p)
@app.post("/prescriptions/{pid}/availability")
def avail(pid: int, db=D, u=U):
    p = rx(db, pid); out = []
    for i in (x for x in p.items if x.verification_status == "VERIFIED"):
        bs = S.usable(db, i.medicine_id); have = sum(b.quantity for b in bs)
        out.append(dict(item_id=i.id, medicine=db.get(Medicine, i.medicine_id).medicine_name, needed=i.quantity, available=have, shortage=max(0, i.quantity - have),
                        batches=[dict(batch_id=b.id, batch_number=b.batch_number, quantity=b.quantity, expiry_date=b.expiry_date, selling_price=float(b.selling_price)) for b in bs]))
    return out
# ---------- dispensing ----------
class Disp(BaseModel): prescription_id: int; confirmed_dispensing: bool = False; discount: float = 0; tax: float = 0
@app.post("/transactions", status_code=201)
def dispense(b: Disp, db=D, u=U):
    if not b.confirmed_dispensing: raise HTTPException(422, "Pharmacist confirmation required")
    p = db.query(Prescription).filter_by(id=b.prescription_id).with_for_update().first()
    if not p: raise HTTPException(404, "Prescription not found")
    if p.status != "VERIFIED": raise HTTPException(409, "Prescription must be VERIFIED before dispensing")
    t = Transaction(prescription_id=p.id, pharmacist_id=u.id); db.add(t); sub = Decimal(0)
    try:
        for i in (x for x in p.items if x.verification_status == "VERIFIED"):
            bs = S.usable(db, i.medicine_id, lock=True)
            if sum(x.quantity for x in bs) < i.quantity: raise HTTPException(409, f"Insufficient usable stock for {db.get(Medicine, i.medicine_id).medicine_name}")
            need = i.quantity
            for bt in bs:
                n = min(bt.quantity, need); bt.quantity -= n; lt = n * bt.selling_price; sub += lt
                t.items.append(TransactionItem(medicine_id=i.medicine_id, batch_id=bt.id, quantity=n, unit_price=bt.selling_price, total_price=lt)); need -= n
                if not need: break
        d, tx = Decimal(str(b.discount)), Decimal(str(b.tax))
        if d < 0 or tx < 0: raise HTTPException(422, "Discount and tax cannot be negative")
        if d > sub: raise HTTPException(422, "Discount cannot exceed subtotal")
        t.subtotal, t.discount, t.tax, t.total_amount = sub, d, tx, sub - d + tx
        p.status = "DISPENSED"; db.flush()
        audit(db, u.id, "PRESCRIPTION_DISPENSED", "Prescription", p.id, f"Tx {t.id} by {u.username}, total {t.total_amount}")
        refresh_alerts(db); db.commit()
    except Exception: db.rollback(); raise
    return receipt(db, t)
def receipt(db, t):
    p = db.get(Prescription, t.prescription_id) if t.prescription_id else None
    return {**row(t), "pharmacist": db.get(User, t.pharmacist_id).username, "prescription_number": p.prescription_number if p else None, "patient_reference": p.patient_reference if p else None,
            "items": [{**row(i), "medicine": db.get(Medicine, i.medicine_id).medicine_name, "batch_number": db.get(Batch, i.batch_id).batch_number} for i in t.items]}
@app.get("/transactions")
def tx_list(limit: int = 50, offset: int = 0, db=D, u=U): return [receipt(db, t) for t in db.query(Transaction).order_by(Transaction.id.desc()).limit(limit).offset(offset)]
@app.get("/transactions/{tid}")
def tx_get(tid: int, db=D, u=U):
    t = db.get(Transaction, tid)
    if not t: raise HTTPException(404)
    return receipt(db, t)
# ---------- images, CSV, reports, edits ----------
@app.get("/prescriptions/{pid}/image")
def rx_image(pid: int, which: str = "original", db=D, u=U):
    p = rx(db, pid); data = p.processed_data if which == "processed" else p.image_data
    if not data: raise HTTPException(404, "Image not available")
    return Response(bytes(data), media_type="image/png" if which == "processed" else "image/jpeg")
CSV_COLS = "medicine_name,generic_name,composition,brand_name,strength,dosage_form,rack_location,shelf_number,reorder_level,mrp,batch_number,quantity,expiry_date,purchase_price,selling_price".split(",")
@app.get("/medicines/sample-csv")
def sample_csv(u=U):
    return Response(",".join(CSV_COLS) + "\nParacetamol 500,Paracetamol,Paracetamol (500mg),Crocin,500 mg,Tablet,Rack A-02,Shelf 3,20,3.50,B2026-01,100,2028-12-31,1.20,2.80\n", media_type="text/csv")
@app.post("/medicines/import-csv")
async def import_csv(file: UploadFile = File(...), db=D, u=U):
    text = (await file.read()).decode("utf-8-sig"); created = updated = batches = 0
    try:
        for r in csv.DictReader(io.StringIO(text)):
            name = (r.get("medicine_name") or "").strip()
            if not name: continue
            f = {k: r[k].strip() for k in ("generic_name", "composition", "brand_name", "strength", "dosage_form", "rack_location", "shelf_number") if r.get(k) and r[k].strip()}
            if r.get("reorder_level"): f["reorder_level"] = int(r["reorder_level"])
            if r.get("mrp"): f["mrp"] = float(r["mrp"])
            m = db.query(Medicine).filter(func.lower(Medicine.medicine_name) == name.lower()).first()
            if m:
                for k, v in f.items(): setattr(m, k, v)
                updated += 1
            else: m = Medicine(medicine_name=name, **f); db.add(m); db.flush(); created += 1
            if r.get("batch_number") and r.get("quantity") and r.get("expiry_date"):
                db.add(Batch(medicine_id=m.id, batch_number=r["batch_number"].strip(), quantity=int(r["quantity"]), expiry_date=dt.date.fromisoformat(r["expiry_date"].strip()),
                             purchase_price=float(r.get("purchase_price") or 0), selling_price=float(r.get("selling_price") or 0))); batches += 1
    except (ValueError, KeyError) as e: db.rollback(); raise HTTPException(422, f"Invalid CSV data: {e}")
    audit(db, u.id, "CSV_IMPORT", "Medicine", None, f"{created} created, {updated} updated, {batches} batches"); refresh_alerts(db); db.commit()
    return dict(created=created, updated=updated, batches=batches)
@app.get("/medicines/{mid}")
def get_med(mid: int, db=D, u=U):
    m = db.get(Medicine, mid)
    if not m: raise HTTPException(404)
    return {**row(m), "usable_stock": S.stock(db, mid)}
@app.put("/medicines/{mid}")
def upd_med(mid: int, b: Med, db=D, a=Depends(admin_only)):
    m = db.get(Medicine, mid)
    if not m: raise HTTPException(404)
    for k, v in b.model_dump(exclude_unset=True).items(): setattr(m, k, v)
    audit(db, a.id, "MEDICINE_UPDATED", "Medicine", mid, m.medicine_name); db.commit(); return row(m)
class BatchUpd(BaseModel): quantity: Optional[int] = None; expiry_date: Optional[dt.date] = None; purchase_price: Optional[float] = None; selling_price: Optional[float] = None
@app.put("/inventory/batch/{bid}")
def upd_batch(bid: int, b: BatchUpd, db=D, u=U):
    x = db.get(Batch, bid)
    if not x: raise HTTPException(404)
    if b.quantity is not None and b.quantity < 0: raise HTTPException(422, "Quantity cannot be negative")
    for k, v in b.model_dump(exclude_none=True).items(): setattr(x, k, v)
    audit(db, u.id, "BATCH_UPDATED", "Batch", bid, str(b.model_dump(exclude_none=True))); refresh_alerts(db); db.commit(); return row(x)
@app.get("/inventory/batches/{mid}")
def med_batches(mid: int, db=D, u=U): return [row(b) for b in db.query(Batch).filter_by(medicine_id=mid).order_by(Batch.expiry_date)]
@app.get("/inventory/{mid}")
def med_stock(mid: int, db=D, u=U):
    m = db.get(Medicine, mid)
    if not m: raise HTTPException(404)
    us = S.stock(db, mid); return dict(usable_units=us, total_units=sum(b.quantity for b in m.batches), low_stock=us <= m.reorder_level)
@app.get("/reports/inventory")
def rep_inv(db=D, u=U):
    return [dict(medicine_id=m.id, name=m.medicine_name, usable=(us := S.stock(db, m.id)), total=sum(b.quantity for b in m.batches), reorder_level=m.reorder_level, low=us <= m.reorder_level) for m in db.query(Medicine)]
@app.get("/reports/sales")
def rep_sales(report_date: Optional[dt.date] = None, db=D, u=U):
    d = report_date or today(); a = dt.datetime.combine(d, dt.time.min, dt.timezone.utc)
    ts = db.query(Transaction).filter(Transaction.created_at >= a, Transaction.created_at < a + dt.timedelta(days=1)).all()
    return dict(date=d, count=len(ts), subtotal=float(sum(t.subtotal for t in ts)), discount=float(sum(t.discount for t in ts)), tax=float(sum(t.tax for t in ts)), total=float(sum(t.total_amount for t in ts)))
@app.get("/reports/prescriptions")
def rep_rx(db=D, u=U): return dict(db.query(Prescription.status, func.count()).group_by(Prescription.status).all())
@app.get("/prescriptions/{pid}/receipt")
def rx_receipt(pid: int, db=D, u=U):
    t = db.query(Transaction).filter_by(prescription_id=pid).order_by(Transaction.id.desc()).first()
    if not t: raise HTTPException(404, "Not dispensed yet")
    return receipt(db, t)
