import os, datetime as dt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import jwt, JWTError
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from .db import get_db, User
SECRET = os.getenv("JWT_SECRET", "change-me-in-production"); ADMIN_CODE = os.getenv("ADMIN_APPROVAL_CODE", "ADMIN_APPROVED_2026")
ph = PasswordHasher(); oauth = OAuth2PasswordBearer(tokenUrl="auth/token")
hash_password = ph.hash
def verify_password(p, h):
    try: return ph.verify(h, p)
    except VerifyMismatchError: return False
def create_token(uid): return jwt.encode({"sub": str(uid), "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=8)}, SECRET, "HS256")
def current_user(tok: str = Depends(oauth), db=Depends(get_db)):
    try: uid = int(jwt.decode(tok, SECRET, ["HS256"])["sub"])
    except (JWTError, ValueError): raise HTTPException(401, "Invalid token")
    u = db.get(User, uid)
    if not u or not u.is_active or not u.is_approved: raise HTTPException(401, "Inactive account")
    return u
def admin_only(u: User = Depends(current_user)):
    if u.role != "ADMIN": raise HTTPException(403, "Admin only")
    return u
