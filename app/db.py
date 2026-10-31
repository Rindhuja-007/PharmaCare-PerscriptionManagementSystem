import datetime as dt, os
from sqlalchemy import *
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, deferred
from sqlalchemy.pool import NullPool
URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or ("sqlite:////tmp/pharmacare.db" if os.getenv("VERCEL") else "sqlite:///./pharmacare.db")
for pre in ("postgres://", "postgresql://"):
    if URL.startswith(pre): URL = "postgresql+psycopg2://" + URL[len(pre):]
if URL.startswith("sqlite"): engine = create_engine(URL, connect_args={"check_same_thread": False})
else: engine = create_engine(URL, poolclass=NullPool, pool_pre_ping=True)
Session = sessionmaker(bind=engine)
Base = declarative_base()
now = lambda: dt.datetime.now(dt.timezone.utc)
today = lambda: dt.date.today()
TS = lambda **k: Column(DateTime(timezone=True), default=now, **k)
def get_db():
    db = Session()
    try: yield db
    finally: db.close()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True); name = Column(String(120), nullable=False)
    username = Column(String(80), unique=True, index=True); email = Column(String(255), unique=True, index=True)
    password_hash = Column(String(255)); role = Column(String(20)); is_active = Column(Boolean, default=True)
    is_approved = Column(Boolean, default=True); approved_by = Column(ForeignKey("users.id"), nullable=True); created_at = TS()
class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True); name = Column(String(200), index=True, nullable=False)
    contact = Column(String(100)); email = Column(String(255)); address = Column(Text); created_at = TS()
class Medicine(Base):
    __tablename__ = "medicines"
    id = Column(Integer, primary_key=True); barcode = Column(String(100), unique=True, index=True)
    medicine_name = Column(String(200), index=True, nullable=False); generic_name = Column(String(200), index=True)
    composition = Column(Text); brand_name = Column(String(200)); strength = Column(String(100)); dosage_form = Column(String(100))
    unit_of_measure = Column(String(50), default="Tablet"); pack_size = Column(Integer, default=1); category = Column(String(100))
    manufacturer = Column(String(200)); prescription_required = Column(Boolean, default=True)
    rack_location = Column(String(100)); shelf_number = Column(String(100))
    storage_condition = Column(String(100), default="Room Temperature"); reorder_level = Column(Integer, default=15)
    mrp = Column(Numeric(10, 2)); hsn_code = Column(String(50)); description = Column(Text)
    created_at = TS(); updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)
    batches = relationship("Batch", back_populates="medicine")
class Batch(Base):
    __tablename__ = "batches"
    __table_args__ = (Index("ix_batches_medicine_expiry", "medicine_id", "expiry_date"),)
    id = Column(Integer, primary_key=True); medicine_id = Column(ForeignKey("medicines.id"), index=True)
    batch_number = Column(String(100), index=True, nullable=False); quantity = Column(Integer, default=0)
    expiry_date = Column(Date, index=True, nullable=False); purchase_price = Column(Numeric(10, 2), nullable=False)
    selling_price = Column(Numeric(10, 2), nullable=False); supplier_id = Column(ForeignKey("suppliers.id"), nullable=True)
    received_date = Column(Date, default=today); reorder_level = Column(Integer, default=0); barcode = Column(String(100))
    medicine = relationship("Medicine", back_populates="batches")
class Prescription(Base):
    __tablename__ = "prescriptions"
    id = Column(Integer, primary_key=True); prescription_number = Column(String(100), unique=True, index=True)
    patient_reference = Column(String(150)); doctor_name = Column(String(150)); image_path = Column(String(500), nullable=False)
    processed_image_path = Column(String(500)); image_data = deferred(Column(LargeBinary)); processed_data = deferred(Column(LargeBinary)); extracted_text = Column(Text); status = Column(String(20), default="UPLOADED")
    confidence_score = Column(Numeric(5, 2)); created_by = Column(ForeignKey("users.id")); verified_by = Column(ForeignKey("users.id"))
    verified_at = Column(DateTime); created_at = TS()
    items = relationship("PrescriptionItem", cascade="all, delete-orphan", order_by="PrescriptionItem.id")
class PrescriptionItem(Base):
    __tablename__ = "prescription_items"
    id = Column(Integer, primary_key=True); prescription_id = Column(ForeignKey("prescriptions.id", ondelete="CASCADE"), index=True)
    medicine_id = Column(ForeignKey("medicines.id"), nullable=True); extracted_medicine_name = Column(String(200), nullable=False)
    matched_medicine_name = Column(String(200)); dosage = Column(String(100)); frequency = Column(String(100))
    duration = Column(String(100)); quantity = Column(Integer); confidence_score = Column(Numeric(5, 2))
    verification_status = Column(String(20), default="PENDING")
class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True); prescription_id = Column(ForeignKey("prescriptions.id"), index=True)
    pharmacist_id = Column(ForeignKey("users.id"), nullable=False)
    subtotal = Column(Numeric(10, 2), default=0); discount = Column(Numeric(10, 2), default=0)
    tax = Column(Numeric(10, 2), default=0); total_amount = Column(Numeric(10, 2), default=0)
    transaction_type = Column(String(50), default="DISPENSING"); created_at = TS(index=True)
    items = relationship("TransactionItem", cascade="all, delete-orphan")
class TransactionItem(Base):
    __tablename__ = "transaction_items"
    id = Column(Integer, primary_key=True); transaction_id = Column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    medicine_id = Column(ForeignKey("medicines.id")); batch_id = Column(ForeignKey("batches.id"), index=True)
    quantity = Column(Integer, nullable=False); unit_price = Column(Numeric(10, 2), nullable=False); total_price = Column(Numeric(10, 2), nullable=False)
class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True); alert_type = Column(String(30)); medicine_id = Column(ForeignKey("medicines.id"), index=True)
    batch_id = Column(ForeignKey("batches.id"), nullable=True); message = Column(String(500), nullable=False)
    severity = Column(String(20)); is_read = Column(Boolean, default=False, index=True); created_at = TS()
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True); user_id = Column(ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), index=True); entity_type = Column(String(100)); entity_id = Column(Integer)
    description = Column(Text); created_at = TS(index=True)
def audit(db, uid, action, etype, eid, desc): db.add(AuditLog(user_id=uid, action=action, entity_type=etype, entity_id=eid, description=desc))
