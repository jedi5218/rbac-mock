import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, organizations, users, resources, roles, resolve, interactions

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
app.include_router(interactions.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
