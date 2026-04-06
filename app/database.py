from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# MySQL database URL
DATABASE_URL = "mysql+pymysql://smartlink:smartlink@localhost/smartlink"

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=True  # Set False in production
)

# Session
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base model
Base = declarative_base()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()