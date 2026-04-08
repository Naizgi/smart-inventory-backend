from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool
from app.config import settings
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure engine with connection pooling settings
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=5,              # Number of connections to keep open
    max_overflow=10,          # Extra connections beyond pool_size
    pool_timeout=30,          # Seconds to wait for a connection
    pool_recycle=3600,        # Recycle connections after 1 hour
    pool_pre_ping=True        # Verify connections before using
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

# Dependency with retry logic for database connection issues
def get_db():
    max_retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        db = None
        try:
            db = SessionLocal()
            # FIXED: Use text() for raw SQL
            db.execute(text("SELECT 1"))
            logger.info(f"Database connection successful (attempt {attempt + 1})")
            yield db
            break  # Success, exit retry loop
            
        except Exception as e:
            logger.error(f"Database connection error (attempt {attempt + 1}/{max_retries}): {e}")
            if db:
                db.rollback()
                db.close()
            
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Max retries reached, failing...")
                raise
        finally:
            if db:
                db.close()

# Optional: Function to check database health
def check_db_health():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False