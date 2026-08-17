from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.connection import engine
s = Session(engine)
r = s.execute(text("SELECT conname, contype FROM pg_constraint WHERE conrelid = 'daily_records'::regclass")).fetchall()
for row in r:
    print(row)
