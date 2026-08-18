import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.db.connection import SessionLocal
from app.dashboard.routes import router as dashboard_router
from app.auth.routes import router as auth_router
from app.farm.routes import router as farm_router

app = FastAPI(title="FurrowCast API")

# CORS origins: comma-separated env var (e.g. Render frontend URL) plus localhost dev.
_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
]
if os.environ.get("CORS_ALLOWED_ORIGINS"):
    _ALLOWED_ORIGINS += [o.strip() for o in os.environ["CORS_ALLOWED_ORIGINS"].split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(farm_router)


@app.get("/health")
def health():
    try:
        db = SessionLocal()
        db.execute(text("SELECT count(*) FROM counties"))
        db.close()
        return {"ok": True, "db": "up"}
    except Exception:
        return {"ok": False, "db": "down"}


@app.get("/")
def index():
    return FileResponse("app/static/login.html")
