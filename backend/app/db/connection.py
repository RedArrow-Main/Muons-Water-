"""Database engine and session factory."""
from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()  # load .env before reading env vars

DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",  # test runner sets this to isolate from dev/prod
    os.environ["DATABASE_URL"],
)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass
