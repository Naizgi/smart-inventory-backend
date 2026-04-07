from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.settings import settings  # import your Settings instance

# Use DATABASE_URL from Pydantic settings
engine = create_engine(
    settings.DATABASE_URL,  # now it will never be None
    echo=False,  # Set True for debugging
)

# Session
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base model
Base = declarative_base()

# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()