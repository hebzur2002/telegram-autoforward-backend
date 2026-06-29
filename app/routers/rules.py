from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, Rule
from app.dependencies import get_current_user

router = APIRouter()

class RuleCreate(BaseModel):
    rule_name: str
    source_chat: str
    target_chat: str
    options: Optional[dict] = {}
    is_enabled: Optional[bool] = True

class RuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    source_chat: Optional[str] = None
    target_chat: Optional[str] = None
    options: Optional[dict] = None
    is_enabled: Optional[bool] = None

def r2d(r):
    return {"id": r.id, "user_id": r.user_id, "rule_name": r.rule_name, "source_chat": r.source_chat, "target_chat": r.target_chat, "options": r.options or {}, "is_enabled": r.is_enabled, "created_at": r.created_at.isoformat() if r.created_at else None}

@router.get("/")
async def get_rules(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(Rule).where(Rule.user_id == user["user_id"]))
    return {"rules": [r2d(r) for r in result.scalars().all()]}

@router.post("/")
async def create_rule(data: RuleCreate, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    rule = Rule(user_id=user["user_id"], rule_name=data.rule_name, source_chat=data.source_chat, target_chat=data.target_chat, options=data.options, is_enabled=data.is_enabled)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return {"success": True, "rule": r2d(rule)}

@router.put("/{rule_id}")
async def update_rule(rule_id: int, data: RuleUpdate, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(Rule).where(Rule.id == rule_id, Rule.user_id == user["user_id"]))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if data.rule_name is not None: rule.rule_name = data.rule_name
    if data.source_chat is not None: rule.source_chat = data.source_chat
    if data.target_chat is not None: rule.target_chat = data.target_chat
    if data.options is not None: rule.options = data.options
    if data.is_enabled is not None: rule.is_enabled = data.is_enabled
    await db.commit()
    await db.refresh(rule)
    return {"success": True, "rule": r2d(rule)}

@router.delete("/{rule_id}")
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(Rule).where(Rule.id == rule_id, Rule.user_id == user["user_id"]))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
    return {"success": True}

@router.patch("/{rule_id}/toggle")
async def toggle_rule(rule_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(Rule).where(Rule.id == rule_id, Rule.user_id == user["user_id"]))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_enabled = not rule.is_enabled
    await db.commit()
    return {"success": True, "is_enabled": rule.is_enabled}
