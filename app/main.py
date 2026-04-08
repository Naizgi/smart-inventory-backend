# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.database import engine, Base, SessionLocal
from app.config import settings
from app.services import SettingsService
from app.seeders.user_seeder import seed_users
from datetime import datetime
import logging

# ==================== LOGGING ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== ROUTES ====================
from app.routes import settings_router
from app.routes import (
    alerts_router, auth_router, branches_router, dashboard_router,
    loan_router, products_router, purchase_router, reports_router,
    sales_router, stock_router, temp_items_router, users_router
)

# ==================== FASTAPI APP ====================
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

# ==================== TRAILING SLASH MIDDLEWARE ====================
@app.middleware("http")
async def remove_trailing_slash(request, call_next):
    """Remove trailing slash from URLs to avoid 307 redirects"""
    path = request.url.path
    
    # Skip for root path and API docs
    if path == "/" or path.startswith("/docs") or path.startswith("/redoc") or path.startswith("/openapi"):
        return await call_next(request)
    
    # Remove trailing slash if present
    if path.endswith("/"):
        new_path = path.rstrip("/")
        new_url = request.url.replace(path=new_path)
        response = await call_next(request)
        return response
    
    return await call_next(request)

# ==================== STARTUP EVENT ====================
@app.on_event("startup")
def startup():
    # Create all tables
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Initialize default settings
        SettingsService.initialize_default_settings(db)
        logger.info("✅ Default settings initialized")

        # Seed users
        seed_users(db)
        logger.info("✅ Users seeded successfully")

    except Exception as e:
        logger.error(f"⚠️ Error during startup: {e}")
    finally:
        db.close()

# ==================== CORS ====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173", 
        "http://localhost:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "https://smartlink.mellainnovation.com",
        "http://smartlink.mellainnovation.com",
        "https://smartlink-inventory.up.railway.app",
        "http://smartlink-inventory.up.railway.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== ROUTERS ====================
app.include_router(auth_router)
app.include_router(branches_router)
app.include_router(products_router)
app.include_router(users_router)
app.include_router(stock_router)
app.include_router(sales_router)
app.include_router(reports_router)
app.include_router(alerts_router)
app.include_router(dashboard_router)
app.include_router(loan_router)
app.include_router(purchase_router)
app.include_router(temp_items_router)
app.include_router(settings_router)

# ==================== ROOT ====================
@app.get("/")
def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }