import datetime as dt, numpy as np, cv2
import app.services as S
from app.db import Session, Medicine, Batch, Prescription, PrescriptionItem, AuditLog
def hdr(c, u, p): return {"Authorization": "Bearer " + c.post("/auth/login", json={"username": u, "password": p}).json()["access_token"]}
def test_extract_returns_only_medicine_lines():
    text = "Dr. y. ngendar rao\nPlot # B9, Sardar Patel Colony\nS' ZoDon Plus\nQutipin 20mg\nPatient Age 45 yrs\nAri van tab\nRivotril 0.5mg"
    assert [item["name"] for item in S.extract(text)] == ["Sizodon Plus", "Qutipin", "Ari van", "Rivotril"]
def test_extract_uses_catalogue_to_recover_ocr_medicine_names():
    text = "Qukpin9omy\nSizodon Plus\nPatient Age 45 yrs"
    assert [item["name"] for item in S.extract(text, ["Qutipin", "Sizodon Plus"])] == ["Qutipin", "Sizodon Plus"]
def test_extract_uses_catalogue_for_noisy_handwritten_lines_with_dosage():
    text = "Tab Qukpin 200mg\nTab S' Zodon Plus\nTab Rivobil 0.5 mg"
    assert [item["name"] for item in S.extract(text)] == ["Qukpin", "Sizodon Plus", "Rivobil"]
def test_extract_reads_schedule_on_following_line_and_calculates_course_quantity():
    items = S.extract("Tab Qutipin 20mg\n1-0-1 x 5 days")
    assert items[0]["frequency"] == "1-0-1"
    assert items[0]["duration"] == "5 days"
    assert items[0]["quantity"] == 10
def test_extract_recovers_five_handwritten_medicines():
    text = "\n".join([
        "Si ZoDon PLus",
        "Qukpin9obmy",
        "ArivanCLor&pm)",
        "Rivobil",
        "SERTA O",
    ])
    items = S.extract(text)
    assert [item["name"] for item in items] == ["Sizodon Plus", "Qutipin", "Ativan", "Rivotril", "Serta"]
    assert [item["dosage"] for item in items] == [None, "200 mg", "2 mg", "0.5 mg", "50 mg"]
def test_extract_attaches_standalone_dosage_to_previous_medicine():
    items = S.extract("Tab Serta\n50 mg")
    assert items[0]["name"] == "Serta"
    assert items[0]["dosage"] == "50 mg"
def test_extract_ignores_catalogue_lines_from_application_screenshot():
    text = "\n".join([
        "PharmaCare",
        "Medicines detected",
        "1. Valparin 500",
        "2. Si ZoDon PLus",
        "3. Qukpin9obmy",
        "200 mg",
        "4. ArivanCLor&pm)",
        "5. Rivobil",
        "0.5 mg",
        "SERTA O",
        "6. Telma 40",
        "Catalogue matches",
        "Medicine to dispense",
    ])
    items = S.extract(text, ["Valparin 500", "Sizodon Plus", "Quetipin 200", "Ativan 2", "Rivotril 0.5", "Telma 40"])
    assert [item["name"] for item in items] == ["Sizodon Plus", "Qutipin", "Ativan", "Rivotril", "Serta"]
    assert [item["dosage"] for item in items] == [None, "200 mg", "2 mg", "0.5 mg", "50 mg"]
def test_full_pipeline_with_receipt(client, monkeypatch):
    monkeypatch.setattr(S, "ocr", lambda data: ("Dr. Rao MBBS\nCity Hospital\n1. Tab Dolo 650 1-0-1 x 5 days Qty 10 tablets\nTab Metformin 500mg BD 30 days #20\nPatient Age 45 yrs", 91.0))
    client.post("/auth/seed-demo"); h = hdr(client, "pharmacist", "Pharmacist@123")
    img = cv2.imencode(".jpg", np.full((200, 300, 3), 255, np.uint8))[1].tobytes()
    r = client.post("/prescriptions/upload", headers=h, files={"file": ("rx.jpg", img, "image/jpeg")}, data={"patient_reference": "Ravi"}); assert r.status_code == 201; pid = r.json()["id"]
    assert client.post(f"/prescriptions/{pid}/preprocess", headers=h).status_code == 200
    assert client.get(f"/prescriptions/{pid}/image?which=processed", headers=h).status_code == 200
    assert client.post(f"/prescriptions/{pid}/process", headers=h).json()["confidence_score"] == 91.0
    items = client.post(f"/prescriptions/{pid}/extract", headers=h).json()
    assert [(i["extracted_medicine_name"], i["frequency"], i["duration"]) for i in items] == [("Dolo 650", "1-0-1", "5 days"), ("Metformin", "BD", "30 days")]
    assert [i["quantity"] for i in items] == [10, 20]
    m = client.post(f"/prescriptions/{pid}/match", headers=h).json()
    assert m[0]["candidates"][0]["name"] == "Dolo 650" and m[1]["candidates"][0]["name"] == "Metformin 500"
    assert any(s["name"] == "Crocin 500" and not s["is_available"] for s in m[0]["substitutes"])
    dec = lambda i, k, q: dict(item_id=items[i]["id"], verification_status="VERIFIED", medicine_id=m[i]["candidates"][0]["medicine_id"], quantity=q)
    assert client.put(f"/prescriptions/{pid}/verify", headers=h, json=dict(items=[dec(0, 0, 10), dec(1, 1, 20)])).json()["status"] == "VERIFIED"
    av = client.post(f"/prescriptions/{pid}/availability", headers=h).json()
    assert all(a["shortage"] == 0 for a in av) and av[0]["batches"][0]["batch_number"] == "DL-2312" and av[0]["batches"][0]["selling_price"] == 2.0
    rc = client.post("/transactions", headers=h, json=dict(prescription_id=pid, confirmed_dispensing=True, discount=1)).json()
    assert abs(rc["total_amount"] - 41) < 0.01 and rc["patient_reference"] == "Ravi" and rc["items"][0]["medicine"] == "Dolo 650"
    assert client.get(f"/prescriptions/{pid}/receipt", headers=h).json()["id"] == rc["id"]
    assert client.get(f"/prescriptions/{pid}", headers=h).json()["status"] == "DISPENSED"
    d = client.get("/reports/dashboard", headers=h).json(); assert d["ready_to_dispense"] == 0 and d["todays_sales"] > 0
def test_ocr_unavailable_gives_clear_error(client, monkeypatch):
    def boom(data): raise ImportError("no engine")
    monkeypatch.setattr(S, "ocr", boom)
    client.post("/auth/seed-demo"); h = hdr(client, "pharmacist", "Pharmacist@123")
    img = cv2.imencode(".jpg", np.full((50, 50, 3), 255, np.uint8))[1].tobytes()
    pid = client.post("/prescriptions/upload", headers=h, files={"file": ("rx.jpg", img, "image/jpeg")}).json()["id"]
    assert client.post(f"/prescriptions/{pid}/process", headers=h).status_code == 503
    mid = client.get("/medicines", headers=h).json()[1]["id"]
    assert client.post(f"/prescriptions/{pid}/items", headers=h, json=dict(extracted_medicine_name="Dolo 650", medicine_id=mid, quantity=5)).status_code == 201
def test_alert_read_state_survives_refresh(client):
    client.post("/auth/seed-demo"); h = hdr(client, "admin", "Admin@123")
    a = client.get("/alerts", headers=h).json(); assert a
    client.put(f"/alerts/{a[0]['id']}/read", headers=h); client.post("/alerts/refresh", headers=h)
    assert len(client.get("/alerts?unread_only=true", headers=h).json()) == len(a) - 1
def make_rx(qty, batches):
    db = Session(); m = Medicine(medicine_name="Testol"); db.add(m); db.flush()
    for n, q, d in batches: db.add(Batch(medicine_id=m.id, batch_number=n, quantity=q, expiry_date=dt.date.today() + dt.timedelta(days=d), purchase_price=1, selling_price=2))
    p = Prescription(prescription_number=f"RX-T{qty}{len(batches)}", image_path="db", status="VERIFIED")
    p.items.append(PrescriptionItem(extracted_medicine_name="Testol", medicine_id=m.id, quantity=qty, verification_status="VERIFIED")); db.add(p); db.commit(); pid = p.id; db.close(); return pid
def qtys():
    db = Session(); r = {b.batch_number: b.quantity for b in db.query(Batch)}; db.close(); return r
def test_fefo_skips_expired_and_requires_confirmation(client):
    client.post("/auth/seed-demo"); h = hdr(client, "pharmacist", "Pharmacist@123")
    pid = make_rx(7, [("late", 5, 200), ("early", 5, 30), ("old", 5, -10)])
    assert client.post("/transactions", headers=h, json=dict(prescription_id=pid)).status_code == 422
    r = client.post("/transactions", headers=h, json=dict(prescription_id=pid, confirmed_dispensing=True, discount=1, tax=2)); assert r.status_code == 201 and r.json()["total_amount"] == 15
    q = qtys(); assert (q["late"], q["early"], q["old"]) == (3, 0, 5)
    assert client.post("/transactions", headers=h, json=dict(prescription_id=pid, confirmed_dispensing=True)).status_code == 409
def test_shortage_and_bad_discount_change_nothing(client):
    client.post("/auth/seed-demo"); h = hdr(client, "pharmacist", "Pharmacist@123")
    pid = make_rx(9, [("a", 5, 100), ("old", 50, -1)])
    assert client.post("/transactions", headers=h, json=dict(prescription_id=pid, confirmed_dispensing=True)).status_code == 409
    pid2 = make_rx(2, [("b", 5, 100)])
    assert client.post("/transactions", headers=h, json=dict(prescription_id=pid2, confirmed_dispensing=True, discount=999)).status_code == 422
    q = qtys(); assert q["a"] == 5 and q["b"] == 5
def test_verify_needs_positive_quantity(client):
    client.post("/auth/seed-demo"); h = hdr(client, "pharmacist", "Pharmacist@123")
    pid = make_rx(1, [("a", 5, 100)]); db = Session(); i = db.query(PrescriptionItem).first(); iid, mid = i.id, i.medicine_id; db.close()
    assert client.put(f"/prescriptions/{pid}/verify", headers=h, json=dict(items=[dict(item_id=iid, verification_status="VERIFIED", medicine_id=mid, quantity=0)])).status_code == 422
def test_csv_import_and_duplicates(client):
    client.post("/auth/seed-demo"); h = hdr(client, "admin", "Admin@123")
    csv_text = client.get("/medicines/sample-csv", headers=h).text
    assert client.post("/medicines/import-csv", headers=h, files={"file": ("m.csv", csv_text)}).json() == dict(created=1, updated=0, batches=1)
    assert client.post("/medicines", headers=h, json=dict(medicine_name="dolo 650")).status_code == 409
