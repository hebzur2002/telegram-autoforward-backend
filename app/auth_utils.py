import jwt
import os
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

SECRET_KEY = os.getenv("JWT_SECRET", "your-super-secret-key")
ENCRYPT_KEY = os.getenv("ENCRYPT_KEY", Fernet.generate_key().decode())
ALGORITHM = "HS256"

fernet = Fernet(ENCRYPT_KEY.encode() if isinstance(ENCRYPT_KEY, str) else ENCRYPT_KEY)

def create_jwt(data: dict, expires_hours: int = 168) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=expires_hours)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_jwt(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

def encrypt_session(session_string: str) -> str:
    return fernet.encrypt(session_string.encode()).decode()

def decrypt_session(encrypted: str) -> str:
    return fernet.decrypt(encrypted.encode()).decode()
