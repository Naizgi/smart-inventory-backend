@staticmethod
def check_low_stock_for_branch(db: Session, branch_id: int):
    """Check low stock and create alerts for a specific branch only"""
    from app.models import Stock, Alert, Product
    from datetime import datetime
    
    # Find all stock items below reorder level for the specific branch
    low_stock_items = db.query(Stock).filter(
        Stock.branch_id == branch_id,
        Stock.quantity < Stock.reorder_level,
        Stock.quantity > 0
    ).all()
    
    alerts_created = 0
    
    for stock in low_stock_items:
        product = db.query(Product).filter(Product.id == stock.product_id).first()
        
        # Check if unresolved alert already exists for this stock
        existing_alert = db.query(Alert).filter(
            Alert.stock_id == stock.id,
            Alert.resolved == False
        ).first()
        
        if not existing_alert:
            # Create new alert
            alert = Alert(
                stock_id=stock.id,
                branch_id=branch_id,
                product_name=product.name,
                current_quantity=stock.quantity,
                reorder_level=stock.reorder_level,
                resolved=False,
                created_at=datetime.now()
            )
            db.add(alert)
            alerts_created += 1
    
    if alerts_created > 0:
        db.commit()
    
    return alerts_created

@staticmethod
def auto_resolve_alerts_for_branch(db: Session, branch_id: int):
    """Auto-resolve alerts for a specific branch when stock is restocked"""
    from app.models import Alert, Stock
    from datetime import datetime
    
    # Get unresolved alerts for the branch
    unresolved_alerts = db.query(Alert).filter(
        Alert.branch_id == branch_id,
        Alert.resolved == False
    ).all()
    
    resolved_count = 0
    
    for alert in unresolved_alerts:
        # Get current stock
        stock = db.query(Stock).filter(Stock.id == alert.stock_id).first()
        
        # If stock has been restocked above reorder level, resolve alert
        if stock and stock.quantity >= stock.reorder_level:
            alert.resolved = True
            alert.resolved_at = datetime.now()
            resolved_count += 1
    
    if resolved_count > 0:
        db.commit()
    
    return resolved_count