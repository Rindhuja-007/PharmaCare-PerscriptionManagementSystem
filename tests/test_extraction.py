from app.db import Session, Medicine
import app.services as S
RAW = """Dr. y. ngendar rao
Plot # B9, Sardar Patel Colony
M.B.3.S (Osm). M.al (Ps, Fi.PS
Hashmathpet Road, Trimulgherry.
SECUNDERABAD - 500 015.
Consultant Nouro - Paychlatrlat
Hegd. No. 8373 (A.P)
Telephone : Resl.040-27796644
Mr SriniuAs
p Chr Scri sapmern
Cournsellad ove Phome
ranm)Dm- HT
S' ZoDon Plus
Pate n-Dels +
totni expil 3moly
ishh
Qukpin 20omg
luishd-
Ari van (lor&pem)
tab
Rivolbil o.smg <clomegpcm)
+ nisw.
Te!
Serra somy
Cell me breeen :
Conhn e
Oho pl s ugewmaau Curas
Dr. Nagendar Rao Y.
(knrkara'w"soany
wugejuokd-oman
4500 015.K.7.
In Emergency / If the doctor Is not avallable, please admit at
Asha Hospital, Road No.14, Banjara
Hills,Hyderabad.Tai:66752222.23542938"""
def test_handwritten_prescription_keeps_only_medicines(client):
    client.post("/auth/seed-demo"); db = Session(); meds = db.query(Medicine).all()
    found = S.parse(RAW, meds)
    assert len(found) == 4, [f["line"] for f in found]
    assert [f["dosage"] for f in found] == [None, "200 mg", None, "0.5 mg"]
    names = {}
    for f in found: c, _ = S.match(db, f["name"], f["dosage"]); names[f["name"]] = c[0]["name"]
    assert sorted(names.values()) == ["Ativan 2", "Qutipin 200", "Rivotril 0.5", "Sizodon Plus"], names
    db.close()
