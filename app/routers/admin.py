from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, User, Session as DBSession, Log, Announcement
from app.dependencies import get_admin_user

router = APIRouter()

class BroadcastRequest(BaseModel):
    message: str

@router.get("/users")
async def get_users(db: AsyncSession = Depends(get_db), admin=Depends(get_admin_user)):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return {"users": [{"id": u.id, "phone": u.phone, "role": u.role, "is_suspended": u.is_suspended, "created_at": u.created_at.isoformat() if u.created_at else None} for u in users]}

@router.patch("/users/{user_id}/suspend")
async def suspend_user(user_id: int, db: AsyncSession = Depends(get_db), admin=Depends(get_admin_user)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_suspended = not user.is_suspended
    await db.commit()
    return {"success": True, "is_suspended": user.is_suspended}

@router.get("/sessions")
async def get_sessions(db: AsyncSession = Depends(get_db), admin=Depends(get_admin_user)):
    result = await db.execute(select(DBSession))
    sessions = result.scalars().all()
    return {"sessions": [{"id": s.id, "user_id": s.user_id, "last_active": s.last_active.isoformat() if s.last_active else None} for s in sessions]}

@router.post("/broadcast")
async def broadcast(req: BroadcastRequest, db: AsyncSession = Depends(get_db), admin=Depends(get_admin_user)):
    announcement = Announcement(message=req.message)
    db.add(announcement)
    await db.commit()
    return {"success": True}

@router.get("/logs")
async def get_system_logs(db: AsyncSession = Depends(get_db), admin=Depends(get_admin_user)):
    result = await db.execute(select(Log).order_by(Log.created_at.desc()).limit(200))
    logs = result.scalars().all()
    return {"logs": [{"id": l.id, "user_id": l.user_id, "status": l.status, "error_reason": l.error_reason, "created_at": l.created_at.isoformat() if l.created_at else None} for l in logs]}
