"""Farm API — CRUD for farm records consumed by the Next.js frontend."""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.db.connection import engine

router = APIRouter(prefix="/api", tags=["farms"])


def _require_user(session_cookie: str | None = Cookie(default=None, alias="session")) -> dict:
    """Dependency — require authenticated user, return user dict."""
    if not session_cookie:
        raise HTTPException(401, "Login required")
    with Session(engine) as s:
        user = get_current_user(s, session_cookie)
    if not user:
        raise HTTPException(401, "Invalid or expired session")
    return user


# ---------------------------------------------------------------------------
# POST /api/farm — create a new farm
# ---------------------------------------------------------------------------
@router.post("/farm")
def create_farm(body: dict, user: dict = Depends(_require_user)):
    """Create a new farm for the current user.

    Body: { county_fips, name, acres?, crop_ids: [str] }
    """
    county_fips = body.get("county_fips", "").strip()
    name = body.get("name", "").strip()
    acres = body.get("acres")
    crop_ids = body.get("crop_ids", [])

    if not county_fips or len(county_fips) != 5:
        raise HTTPException(400, "county_fips must be a 5-digit FIPS code")
    if not name:
        raise HTTPException(400, "Farm name is required")
    if not crop_ids:
        raise HTTPException(400, "At least one crop is required")

    with Session(engine) as s:
        # Verify county exists
        county = s.execute(text(
            "SELECT fips FROM counties WHERE fips = :f"
        ), {"f": county_fips}).fetchone()
        if not county:
            raise HTTPException(404, f"County {county_fips} not found")

        # Check for existing farm with same user + county
        existing = s.execute(text(
            "SELECT id FROM farms WHERE user_id = :uid AND county_fips = :fips"
        ), {"uid": user["id"], "fips": county_fips}).fetchone()
        if existing:
            raise HTTPException(409, "You already have a farm in this county")

        # Verify all crops exist
        for cid in crop_ids:
            crop = s.execute(text(
                "SELECT id FROM crops WHERE id = :cid"
            ), {"cid": cid}).fetchone()
            if not crop:
                raise HTTPException(404, f"Crop '{cid}' not found")

        # Insert farm
        s.execute(text(
            "INSERT INTO farms (user_id, county_fips, name, acres) "
            "VALUES (:uid, :fips, :name, :acres)"
        ), {"uid": user["id"], "fips": county_fips, "name": name, "acres": acres})
        s.commit()

        farm = s.execute(text(
            "SELECT id FROM farms WHERE user_id = :uid AND county_fips = :fips"
        ), {"uid": user["id"], "fips": county_fips}).fetchone()
        farm_id = farm[0]

        # Insert crop associations
        for cid in crop_ids:
            s.execute(text(
                "INSERT INTO farm_crops (farm_id, crop_id) VALUES (:fid, :cid)"
            ), {"fid": farm_id, "cid": cid})
        s.commit()

    return {"id": farm_id, "county_fips": county_fips, "name": name,
            "acres": acres, "crops": crop_ids}


# ---------------------------------------------------------------------------
# GET /api/farm — list all farms for current user
# ---------------------------------------------------------------------------
@router.get("/farm")
def list_farms(user: dict = Depends(_require_user)):
    """Return all farms for the current user."""
    with Session(engine) as s:
        rows = s.execute(text(
            "SELECT f.id, f.county_fips, f.name, f.acres, f.created_at "
            "FROM farms f WHERE f.user_id = :uid ORDER BY f.created_at"
        ), {"uid": user["id"]}).fetchall()

        farms = []
        for r in rows:
            crops = s.execute(text(
                "SELECT crop_id FROM farm_crops WHERE farm_id = :fid ORDER BY crop_id"
            ), {"fid": r[0]}).fetchall()
            farms.append({
                "id": r[0],
                "county_fips": r[1],
                "name": r[2],
                "acres": float(r[3]) if r[3] else None,
                "created_at": str(r[4]),
                "crops": [c[0] for c in crops],
            })
    return farms


# ---------------------------------------------------------------------------
# DELETE /api/farm/{farm_id} — remove a farm
# ---------------------------------------------------------------------------
@router.delete("/farm/{farm_id}")
def delete_farm(farm_id: int, user: dict = Depends(_require_user)):
    """Delete a farm owned by the current user."""
    with Session(engine) as s:
        farm = s.execute(text(
            "SELECT id FROM farms WHERE id = :fid AND user_id = :uid"
        ), {"fid": farm_id, "uid": user["id"]}).fetchone()
        if not farm:
            raise HTTPException(404, "Farm not found")

        s.execute(text("DELETE FROM farm_crops WHERE farm_id = :fid"), {"fid": farm_id})
        s.execute(text("DELETE FROM farms WHERE id = :fid"), {"fid": farm_id})
        s.commit()
    return {"ok": True}
