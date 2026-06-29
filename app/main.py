from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, rules, logs, admin, worker
from app.database import init_db
import asyncio

app = FastAPI(title="Telegram Auto Forward API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(rules.router, prefix="/rules", tags=["rules"])
app.include_router(logs.router, prefix="/logs", tags=["logs"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(worker.router, prefix="/worker", tags=["worker"])

@app.on_event("startup")
async def startup():
    await init_db()
    from app.services.forwarder import start_all_workers
    asyncio.create_task(start_all_workers())

@app.get("/")
async def root():
    return {"status": "running"}

@app.get("/health")
async def health():
    return {"status": "ok"}
