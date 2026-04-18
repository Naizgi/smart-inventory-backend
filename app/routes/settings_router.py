from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from app.database import get_db
from app.services import SettingsService
from app.utils.dependencies import require_admin
from app.models import User
from pydantic import BaseModel

router = APIRouter(prefix="/api/settings", tags=["Settings"])

class SettingsUpdateRequest(BaseModel):
    settings: Dict[str, Any]

# ==================== GENERAL SETTINGS ====================

# GET - General settings (handle both with and without trailing slash)
@router.get("/general")   # No slash - /api/settings/general
@router.get("/general/")  # With slash - /api/settings/general/
def get_general_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get general system settings"""
    try:
        settings = SettingsService.get_category_settings(db, "general")
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# PUT - General settings (handle both with and without trailing slash)
@router.put("/general")   # No slash - /api/settings/general
@router.put("/general/")  # With slash - /api/settings/general/
def update_general_settings(
    data: SettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update general system settings"""
    try:
        SettingsService.set_multiple_settings(db, "general", data.settings, current_user.id)
        return {"message": "General settings updated successfully", "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== NOTIFICATION SETTINGS ====================

# GET - Notification settings (handle both with and without trailing slash)
@router.get("/notifications")   # No slash - /api/settings/notifications
@router.get("/notifications/")  # With slash - /api/settings/notifications/
def get_notification_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get notification settings"""
    try:
        settings = SettingsService.get_category_settings(db, "notification")
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# PUT - Notification settings (handle both with and without trailing slash)
@router.put("/notifications")   # No slash - /api/settings/notifications
@router.put("/notifications/")  # With slash - /api/settings/notifications/
def update_notification_settings(
    data: SettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update notification settings"""
    try:
        SettingsService.set_multiple_settings(db, "notification", data.settings, current_user.id)
        return {"message": "Notification settings updated successfully", "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== BACKUP SETTINGS ====================

# GET - Backup settings (handle both with and without trailing slash)
@router.get("/backup")   # No slash - /api/settings/backup
@router.get("/backup/")  # With slash - /api/settings/backup/
def get_backup_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get backup settings"""
    try:
        settings = SettingsService.get_category_settings(db, "backup")
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# PUT - Backup settings (handle both with and without trailing slash)
@router.put("/backup")   # No slash - /api/settings/backup
@router.put("/backup/")  # With slash - /api/settings/backup/
def update_backup_settings(
    data: SettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update backup settings"""
    try:
        SettingsService.set_multiple_settings(db, "backup", data.settings, current_user.id)
        return {"message": "Backup settings updated successfully", "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== BACKUP MANAGEMENT ====================

# POST - Create backup (handle both with and without trailing slash)
@router.post("/backup/create")   # No slash - /api/settings/backup/create
@router.post("/backup/create/")  # With slash - /api/settings/backup/create/
def create_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a manual database backup"""
    try:
        backup = SettingsService.create_backup(db, current_user.id)
        return backup
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# GET - Get backups list (handle both with and without trailing slash)
@router.get("/backups")   # No slash - /api/settings/backups
@router.get("/backups/")  # With slash - /api/settings/backups/
def get_backups(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get recent backups list"""
    try:
        backups = SettingsService.get_backups(db, limit)
        return backups
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# DELETE by ID - no change needed (already has slash before ID)
@router.delete("/backups/{backup_id}")
def delete_backup(
    backup_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete a backup file"""
    try:
        success = SettingsService.delete_backup(db, backup_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Backup not found")
        return {"message": "Backup deleted successfully", "success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== CACHE MANAGEMENT ====================

# POST - Clear cache (handle both with and without trailing slash)
@router.post("/cache/clear")   # No slash - /api/settings/cache/clear
@router.post("/cache/clear/")  # With slash - /api/settings/cache/clear/
def clear_cache(
    current_user: User = Depends(require_admin)
):
    """Clear application cache"""
    try:
        result = SettingsService.clear_cache()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== SYSTEM INFORMATION ====================

# GET - System info (handle both with and without trailing slash)
@router.get("/system/info")   # No slash - /api/settings/system/info
@router.get("/system/info/")  # With slash - /api/settings/system/info/
def get_system_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get system information and statistics"""
    try:
        info = SettingsService.get_system_info(db)
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== DATA MANAGEMENT ====================

# POST - Reset system data (handle both with and without trailing slash)
@router.post("/system/reset")   # No slash - /api/settings/system/reset
@router.post("/system/reset/")  # With slash - /api/settings/system/reset/
def reset_system_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Reset all system data (DANGER: This will delete all transactional data)"""
    try:
        result = SettingsService.reset_system_data(db, current_user.id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# POST - Export data (handle both with and without trailing slash)
@router.post("/system/export")   # No slash - /api/settings/system/export
@router.post("/system/export/")  # With slash - /api/settings/system/export/
def export_all_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Export all system data as JSON"""
    try:
        data = SettingsService.export_all_data(db)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
    # Add this to your settings.py or create a new route file
@router.get("/bank-accounts/public")
def get_public_bank_accounts(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)  # Allow both admin and salesman
):
    """Get bank accounts for POS transactions (accessible by all authenticated users)"""
    try:
        # Get bank accounts from general settings
        settings = SettingsService.get_category_settings(db, "general")
        
        bank_accounts = []
        if settings.get("bank_accounts"):
            if isinstance(settings["bank_accounts"], list):
                bank_accounts = settings["bank_accounts"]
            elif isinstance(settings["bank_accounts"], str):
                import json
                try:
                    bank_accounts = json.loads(settings["bank_accounts"])
                except:
                    bank_accounts = []
        
        # Return only active bank accounts
        active_accounts = [acc for acc in bank_accounts if acc.get("is_active", True)]
        
        return active_accounts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))