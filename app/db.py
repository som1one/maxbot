from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


engine_kwargs = {
    "pool_pre_ping": True,
    "echo": False,
}

if settings.sqlalchemy_database_url.startswith("postgresql"):
    engine_kwargs["connect_args"] = {"options": "-c timezone=utc"}


engine = create_engine(settings.sqlalchemy_database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
