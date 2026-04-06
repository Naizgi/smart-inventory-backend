from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.services import AlertService
from app.schemas import AlertResponse
from app.utils.dependencies import require_admin

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])

@router.get("/", response_model=List[AlertResponse])
def get_alerts(
    resolved: bool = Query(False),
    branch_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get alerts (Admin only)"""
    alerts = AlertService.get_alerts(db, resolved, branch_id)
    return alerts

@router.post("/{alert_id}/resolve")
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Resolve an alert (Admin only)"""
    alert = AlertService.resolve_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert resolved successfully"}




@router.post("/check-low-stock")
def check_low_stock_manual(
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Manually trigger low stock check and create alerts"""
    try:
        alerts_created = AlertService.check_low_stock_and_create_alerts(db)
        resolved_count = AlertService.auto_resolve_alerts(db)
        
        return {
            "message": "Low stock check completed",
            "alerts_created": alerts_created,
            "alerts_resolved": resolved_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/low-stock-summary")
def get_low_stock_summary(
    branch_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get summary of all low stock items"""
    try:
        summary = AlertService.get_low_stock_summary(db, branch_id)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))