import asyncio, os
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.database import Rule, Log, Session as DBSession, User

API_ID = int(os.getenv("TELEGRAM_API_ID", "37545301"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "afe693a2e3b828f9f4276a96aa1b9201")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./autoforward.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
active_workers = {}

def get_worker_status():
    return [{"user_id": uid, "connected": c.is_connected()} for uid, c in active_workers.items()]

def apply_filters(text, options):
    if not text: return text
    for kw in options.get("keyword_include", []):
        if kw.lower() not in text.lower(): return None
    for kw in options.get("keyword_exclude", []):
        if kw.lower() in text.lower(): return None
    for f, r in options.get("text_replacement", {}).items():
        text = text.replace(f, r)
    return f"{options.get('prefix','')}{text}{options.get('suffix','')}"

async def save_log(user_id, rule_id, source, target, msg_type, status, error=None):
    async with AsyncSessionLocal() as db:
        db.add(Log(user_id=user_id, rule_id=rule_id, source=str(source), target=str(target), message_type=msg_type, status=status, error_reason=error, created_at=datetime.utcnow()))
        await db.commit()

async def run_worker_for_user(user_id, session_string):
    client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
    active_workers[user_id] = client
    try:
        await client.connect()
        if not await client.is_user_authorized(): return
        async def get_rules():
            async with AsyncSessionLocal() as db:
                r = await db.execute(select(Rule).where(Rule.user_id == user_id, Rule.is_enabled == True))
                return r.scalars().all()
        @client.on(events.NewMessage())
        async def handler(event):
            try:
                rules = await get_rules()
                chat_id = event.chat_id
                chat_username = getattr(event.chat, 'username', None)
                for rule in rules:
                    src = rule.source_chat.strip().lstrip("@")
                    if str(chat_id) != str(rule.source_chat) and (not chat_username or chat_username.lower() != src.lower()): continue
                    options = rule.options or {}
                    if options.get("delay"): await asyncio.sleep(options["delay"])
                    if options.get("media_only") and not event.message.media: continue
                    target = rule.target_chat.strip()
                    msg_type = type(event.message.media).__name__ if event.message.media else "text"
                    try:
                        text = apply_filters(event.message.text or "", options)
                        if text is None: continue
                        if event.message.media and options.get("preserve_media", True):
                            await client.send_file(target, event.message.media, caption=text if options.get("preserve_caption", True) else "")
                        elif text:
                            await client.send_message(target, text)
                        await save_log(user_id, rule.id, rule.source_chat, target, msg_type, "success")
                    except FloodWaitError as e:
                        await asyncio.sleep(e.seconds)
                        await save_log(user_id, rule.id, rule.source_chat, target, msg_type, "failed", f"FloodWait {e.seconds}s")
                    except Exception as e:
                        await save_log(user_id, rule.id, rule.source_chat, target, msg_type, "failed", str(e))
            except Exception as e:
                print(f"Handler error: {e}")
        await client.run_until_disconnected()
    except Exception as e:
        print(f"Worker error user {user_id}: {e}")
    finally:
        active_workers.pop(user_id, None)

async def start_all_workers():
    await asyncio.sleep(2)
    try:
        from app.auth_utils import decrypt_session
        async with AsyncSessionLocal() as db:
            users = (await db.execute(select(User).where(User.is_suspended == False))).scalars().all()
            for user in users:
                session = (await db.execute(select(DBSession).where(DBSession.user_id == user.id).order_by(DBSession.last_active.desc()).limit(1))).scalar_one_or_none()
                if session:
                    try: asyncio.create_task(run_worker_for_user(user.id, decrypt_session(session.session_string)))
                    except Exception as e: print(f"Startup worker error: {e}")
    except Exception as e:
        print(f"start_all_workers error: {e}")

async def restart_user_worker(user_id, db):
    if user_id in active_workers:
        try: await active_workers[user_id].disconnect()
        except: pass
        active_workers.pop(user_id, None)
    await asyncio.sleep(1)
    from app.auth_utils import decrypt_session
    session = (await db.execute(select(DBSession).where(DBSession.user_id == user_id).order_by(DBSession.last_active.desc()).limit(1))).scalar_one_or_none()
    if session:
        try: asyncio.create_task(run_worker_for_user(user_id, decrypt_session(session.session_string)))
        except Exception as e: print(f"Restart error: {e}")
