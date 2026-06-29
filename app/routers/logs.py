from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database import get_db, Log
from app.dependencies import get_current_user

router = APIRouter()

@router.get("/")
async def get_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=200),
    status: str = Query(None),
    rule_id: int = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    query = select(Log).where(Log.user_id == user["user_id"])
    if status:
        query = query.where(Log.status == status)
    if rule_id:
        query = query.where(Log.rule_id == rule_id)
    query = query.order_by(desc(Log.created_at)).offset((page-1)*limit).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()
    return {"logs": [{"id": l.id, "rule_id": l.rule_id, "source": l.source, "target": l.target, "message_type": l.message_type, "status": l.status, "error_reason": l.error_reason, "created_at": l.created_at.isoformat() if l.created_at else None} for l in logs], "page": page}
