from sqlalchemy.orm import Session
from app.db.connection import engine
from app.advisor.service import generate_all

result = generate_all("2026-08-10")
print("Counties processed:", result["counties_processed"])
print("Advisories generated:", result["advisories_generated"])
print("Errors:", result["errors"])
