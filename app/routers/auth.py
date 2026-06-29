from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, User, Session as DBSession
from app.auth_utils import create_jwt, encrypt_session
import os

router = APIRouter()
API_ID = int(os.getenv("TELEGRAM_API_ID", "37545301"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "afe693a2e3b828f9f4276a96aa1b9201")
pending_auths = {}

class SendOTPRequest(BaseModel):
    phone: str

class VerifyOTPRequest(BaseModel):
    phone: str
    code: str
    password: str | None = None

@router.post("/send-otp")
async def send_otp(req: SendOTPRequest):
    phone = req.phone.strip()
    if not phone.startswith("+"): phone = "+" + phone
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    try:
        await client.connect()
        result = await client.send_code_request(phone)
        pending_auths[phone] = {"phone_code_hash": result.phone_code_hash, "session": client.session.save()}
        await client.disconnect()
        return {"success": True, "message": "OTP sent"}
    except Exception as e:
        await client.disconnect()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/verify-otp")
async def verify_otp(req: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    phone = req.phone.strip()
    if not phone.startswith("+"): phone = "+" + phone
    if phone not in pending_auths:
        raise HTTPException(status_code=400, detail="Send OTP first")
    auth_data = pending_auths[phone]
    client = TelegramClient(StringSession(auth_data["session"]), API_ID, API_HASH)
    try:
        await client.connect()
        try:
            await client.sign_in(phone=phone, code=req.code, phone_code_hash=auth_data["phone_code_hash"])
        except SessionPasswordNeededError:
            if not req.password:
                await client.disconnect()
                return {"requires_2fa": True}
            await client.sign_in(password=req.password)
        except PhoneCodeInvalidError:
            await client.disconnect()
            raise HTTPException(status_code=400, detail="Invalid OTP")
        session_str = client.session.save()
        await client.disconnect()
        result = await db.execute(select(User).where(User.phone == phone))
        user = result.scalar_one_or_none()
        if not user:
            user = User(phone=phone)
            db.add(user)
            await db.commit()
            await db.refresh(user)
        from app.auth_utils import encrypt_session
        db_session = DBSession(user_id=user.id, session_string=encrypt_session(session_str))
        db.add(db_session)
        await db.commit()
        pending_auths.pop(phone, None)
        token = create_jwt({"user_id": user.id, "phone": phone, "role": user.role})
        return {"success": True, "token": token, "user": {"id": user.id, "phone": phone, "role": user.role}}
    except HTTPException:
        raise
    except Exception as e:
        await client.disconnect()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/logout")
async def logout():
    return {"success": True}
