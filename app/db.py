from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Hardcoded DB URL for Docker environment
DB_URL = "postgresql+psycopg2://kvt:kvtpassword@db:5432/kvtservice"

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    connect_args={"options": "-c timezone=utc"},
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
