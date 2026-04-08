from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create engine with connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def get_db():
    """Dependency that provides database session with retry logic"""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        db = None
        try:
            db = SessionLocal()
            # Test connection using text() for raw SQL
            db.execute(text("SELECT 1"))
            yield db
            break
            
        except Exception as e:
            logger.error(f"DB error (attempt {attempt + 1}): {e}")
            if db:
                db.rollback()
                db.close()
            
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise
        finally:
            if db:
                db.close()