from fastapi import APIRouter
from app.services.forwarder import get_worker_status

router = APIRouter()

@router.get("/status")
async def worker_status():
    status = get_worker_status()
    return {
    "online": True,
    "active_workers": status
}
