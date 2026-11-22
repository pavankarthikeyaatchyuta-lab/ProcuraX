import os
from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def uid():
    return uuid4().hex


def today():
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


class Base(DeclarativeBase):
    pass


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./procurement.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
    pool_pre_ping=True,
)
if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def sqlite_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db
