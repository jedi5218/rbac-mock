import asyncio
import os
import time

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import invalidate_all
from app.database import AsyncSessionLocal, get_db
from app.routers import auth, organizations, users, resources, roles, resolve, exchanges
from app.seed import reset as seed_reset

app = FastAPI(title="RBAC Mockup", version="0.1.0")

cors_origins = os.environ.get(
    "CORS_ORIGINS", "http://localhost:5173,http://frontend:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(organizations.router)
app.include_router(users.router)
app.include_router(resources.router)
app.include_router(roles.router)
app.include_router(resolve.router)
app.include_router(exchanges.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Demo reset ───────────────────────────────────────────────────────────────

_last_reset = 0.0


@app.post("/reset")
async def reset_demo(db: AsyncSession = Depends(get_db)):
    global _last_reset
    now = time.time()
    if now - _last_reset < 30:
        raise HTTPException(429, "Reset rate limited — try again in 30 seconds")
    _last_reset = now
    await seed_reset(db)
    invalidate_all()
    return {"status": "reset complete"}


async def _scheduled_reset_loop():
    """Reset DB at 02:00 UTC daily."""
    from datetime import datetime, timezone, timedelta

    while True:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        try:
            async with AsyncSessionLocal() as db:
                await seed_reset(db)
                invalidate_all()
        except Exception:
            pass  # best-effort; next day will retry


@app.on_event("startup")
async def _start_scheduled_reset():
    asyncio.create_task(_scheduled_reset_loop())
