from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from app.database import get_db
from app.models import User, Stock, Product, Branch, StockMovement
from app.schemas import StockResponse
from app.utils.dependencies import require_admin, get_current_user

router = APIRouter(prefix="/api/stock", tags=["Stock"])

@router.get("/{branch_id}")
def get_branch_stock(
    branch_id: int,
    low_stock: bool = Query(False),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)  # Changed from require_admin to get_current_user
):
    """Get stock for a specific branch (Admin can view any branch, Salesman can view their own branch)"""
    
    try:
        # Check if branch exists
        branch = db.query(Branch).filter(Branch.id == branch_id).first()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")
        
        # Permission check: Admin can view any branch, Salesman can only view their own branch
        if current_user.role == "salesman" and current_user.branch_id != branch_id:
            raise HTTPException(status_code=403, detail="Not authorized to view this branch")
        
        # Get all stock items for this branch
        stocks = db.query(Stock).filter(Stock.branch_id == branch_id).all()
        
        result = []
        for stock in stocks:
            product = db.query(Product).filter(Product.id == stock.product_id).first()
            if not product:
                continue
            
            # Determine status
            if stock.quantity <= 0:
                status = "out_of_stock"
            elif stock.quantity <= stock.reorder_level:
                status = "low"
            else:
                status = "normal"
            
            # Apply low stock filter
            if low_stock and status != "low":
                continue
            
            # Return the correct format expected by StockResponse schema
            result.append({
                "product_id": product.id,
                "product_name": product.name,
                "product_sku": product.sku,
                "quantity": float(stock.quantity),
                "reorder_level": float(stock.reorder_level),
                "status": status
            })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_branch_stock: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[StockResponse])
def get_my_branch_stock(
    low_stock: bool = Query(False),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get stock for the current user's branch (for salesman)"""
    
    try:
        # Salesman must have a branch assigned
        if not current_user.branch_id:
            raise HTTPException(status_code=400, detail="User not assigned to a branch")
        
        # Get all stock items for the user's branch
        stocks = db.query(Stock).filter(Stock.branch_id == current_user.branch_id).all()
        
        result = []
        for stock in stocks:
            product = db.query(Product).filter(Product.id == stock.product_id).first()
            if not product:
                continue
            
            # Determine status
            if stock.quantity <= 0:
                status = "out_of_stock"
            elif stock.quantity <= stock.reorder_level:
                status = "low"
            else:
                status = "normal"
            
            # Apply low stock filter
            if low_stock and status != "low":
                continue
            
            result.append({
                "product_id": product.id,
                "product_name": product.name,
                "product_sku": product.sku,
                "quantity": float(stock.quantity),
                "reorder_level": float(stock.reorder_level),
                "status": status
            })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_my_branch_stock: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{branch_id}/{product_id}/add")
def add_stock(
    branch_id: int,
    product_id: int,
    quantity: float = Query(..., gt=0),
    notes: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Add stock to a branch (Admin only)"""
    
    try:
        # Check if branch exists
        branch = db.query(Branch).filter(Branch.id == branch_id).first()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")
        
        # Check if product exists
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Get or create stock record
        stock = db.query(Stock).filter(
            Stock.branch_id == branch_id,
            Stock.product_id == product_id
        ).first()
        
        if stock:
            stock.quantity += quantity
        else:
            stock = Stock(
                branch_id=branch_id,
                product_id=product_id,
                quantity=quantity,
                reorder_level=10
            )
            db.add(stock)
        
        # Record stock movement
        stock_movement = StockMovement(
            branch_id=branch_id,
            product_id=product_id,
            user_id=current_user.id,
            change_qty=quantity,
            movement_type="purchase",
            notes=notes or f"Stock added by {current_user.name}"
        )
        db.add(stock_movement)
        
        db.commit()
        db.refresh(stock)
        
        return {
            "success": True,
            "message": f"Added {quantity} units of {product.name}",
            "product_id": product_id,
            "branch_id": branch_id,
            "new_quantity": float(stock.quantity)
        }
        
    except Exception as e:
        db.rollback()
        print(f"Error in add_stock: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/initialize/{branch_id}")
def initialize_branch_stock(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Initialize stock for all products in a branch"""
    
    try:
        # Check if branch exists
        branch = db.query(Branch).filter(Branch.id == branch_id).first()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")
        
        # Get all active products
        products = db.query(Product).filter(Product.active == True).all()
        
        created_count = 0
        for product in products:
            existing = db.query(Stock).filter(
                Stock.branch_id == branch_id,
                Stock.product_id == product.id
            ).first()
            
            if not existing:
                stock = Stock(
                    branch_id=branch_id,
                    product_id=product.id,
                    quantity=0,
                    reorder_level=10
                )
                db.add(stock)
                created_count += 1
        
        db.commit()
        
        return {
            "message": f"Initialized stock for {created_count} products in branch {branch.name}",
            "branch_id": branch_id,
            "branch_name": branch.name,
            "products_initialized": created_count
        }
        
    except Exception as e:
        db.rollback()
        print(f"Error in initialize_branch_stock: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))