from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base, SessionLocal
from app.config import settings
from app.services import SettingsService
from datetime import datetime

# ==================== ROUTES ====================
from app.routes import (
    auth_router,
    branches_router,
    products_router,
    users_router,
    stock_router,
    sales_router,
    reports_router,
    alerts_router,
    dashboard_router,
    loan_router,
    purchase_router,
    temp_items_router,
    settings_router
)

# ==================== DATABASE SETUP ====================

# Create tables (OK for now, later use Alembic)
Base.metadata.create_all(bind=engine)

# Initialize default settings
def init_settings():
    db = SessionLocal()
    try:
        SettingsService.initialize_default_settings(db)
        print("✅ Default settings initialized")
    except Exception as e:
        print(f"⚠️ Error initializing settings: {e}")
    finally:
        db.close()

init_settings()

# ==================== FASTAPI APP ====================

fastapi_app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

# ==================== CORS ====================

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "https://smartlink.mellainnovation.com/api",
        # 🔥 ADD YOUR DOMAIN HERE AFTER DEPLOY
        # "https://yourdomain.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ==================== ROUTERS ====================

fastapi_app.include_router(auth_router)
fastapi_app.include_router(branches_router)
fastapi_app.include_router(products_router)
fastapi_app.include_router(users_router)
fastapi_app.include_router(stock_router)
fastapi_app.include_router(sales_router)
fastapi_app.include_router(reports_router)
fastapi_app.include_router(alerts_router)
fastapi_app.include_router(dashboard_router)
fastapi_app.include_router(loan_router)
fastapi_app.include_router(purchase_router)
fastapi_app.include_router(temp_items_router)
fastapi_app.include_router(settings_router)

# ==================== ROOT ====================

@fastapi_app.get("/")
def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }

@fastapi_app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# ==================== CPANEL FIX (VERY IMPORTANT) ====================

from asgiref.wsgi import WsgiToAsgi

app = WsgiToAsgi(fastapi_app)