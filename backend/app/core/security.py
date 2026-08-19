from datetime import datetime, timedelta, timezone
import jwt
from fastapi import HTTPException, status
from pwdlib import PasswordHash
from .config import settings
password_hash = PasswordHash.recommended()
def hash_password(value: str) -> str: return password_hash.hash(value)
def verify_password(value: str, hashed: str) -> bool: return password_hash.verify(value, hashed)
def create_token(subject: str, roles: list[str]) -> str:
    payload = {"sub": subject, "roles": roles, "exp": datetime.now(timezone.utc)+timedelta(minutes=settings().jwt_expire_minutes)}
    return jwt.encode(payload, settings().jwt_secret, algorithm="HS256")
def decode_token(token: str) -> dict:
    try: return jwt.decode(token, settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")
