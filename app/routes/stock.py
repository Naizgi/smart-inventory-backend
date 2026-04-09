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

# GET by branch ID - no change needed (has slash before ID)
@router.get("/{branch_id}")
def get_branch_stock(
    branch_id: int,
    low_stock: bool = Query(False),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
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

# GET - Get my branch stock (handle both with and without trailing slash)
@router.get("", response_model=List[StockResponse])   # No slash - /api/stock
@router.get("/", response_model=List[StockResponse])  # With slash - /api/stock/
def get_my_branch_stock(
    low_stock: bool = Query(False),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get stock for the current user's branch (for salesman)"""
    
    try:
        # User must have a branch assigned
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

# POST - Add stock (Modified to allow both admin and sales)
# POST - Add stock (Modified to allow both admin and sales)
@router.post("/{branch_id}/{product_id}/add")   # No trailing slash
@router.post("/{branch_id}/{product_id}/add/")  # With trailing slash
def add_stock(
    branch_id: int,
    product_id: int,
    quantity: float = Query(..., gt=0),
    notes: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Add stock to a branch
    
    - Admin: Can add stock to any branch
    - Salesman: Can only add stock to their own branch
    """
    
    try:
        print(f"=== ADD STOCK DEBUG ===")
        print(f"Branch ID: {branch_id}")
        print(f"Product ID: {product_id}")
        print(f"Quantity: {quantity}")
        print(f"Notes: {notes}")
        print(f"Current User ID: {current_user.id}")
        print(f"Current User Role: {current_user.role}")
        print(f"Current User Branch ID: {current_user.branch_id}")
        
        # Check if branch exists
        branch = db.query(Branch).filter(Branch.id == branch_id).first()
        if not branch:
            print(f"Branch {branch_id} not found")
            raise HTTPException(status_code=404, detail="Branch not found")
        
        print(f"Branch found: {branch.name}")
        
        # Check if product exists
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            print(f"Product {product_id} not found")
            raise HTTPException(status_code=404, detail="Product not found")
        
        print(f"Product found: {product.name}")
        
        # Permission check: Salesman can only add stock to their own branch
        if current_user.role == "salesman":
            if not current_user.branch_id:
                raise HTTPException(status_code=400, detail="User not assigned to a branch")
            if current_user.branch_id != branch_id:
                raise HTTPException(status_code=403, detail="Not authorized to add stock to this branch")
            print("Salesman permission check passed")
        
        # Get or create stock record
        stock = db.query(Stock).filter(
            Stock.branch_id == branch_id,
            Stock.product_id == product_id
        ).first()
        
        from decimal import Decimal
        
        if stock:
            old_quantity = float(stock.quantity)
            # Convert Decimal to float for addition, then back to Decimal for storage
            stock.quantity = Decimal(str(float(stock.quantity) + quantity))
            print(f"Updated existing stock: {old_quantity} -> {float(stock.quantity)}")
        else:
            stock = Stock(
                branch_id=branch_id,
                product_id=product_id,
                quantity=Decimal(str(quantity)),
                reorder_level=10
            )
            db.add(stock)
            print(f"Created new stock record with quantity: {quantity}")
        
        # Record stock movement
        stock_movement = StockMovement(
            branch_id=branch_id,
            product_id=product_id,
            user_id=current_user.id,
            change_qty=Decimal(str(quantity)),
            movement_type="purchase",
            notes=notes or f"Stock added by {current_user.name} (Role: {current_user.role})"
        )
        db.add(stock_movement)
        print(f"Created stock movement record")
        
        # Commit the transaction
        db.commit()
        print("Database commit successful")
        
        db.refresh(stock)
        
        response_data = {
            "success": True,
            "message": f"Added {quantity} units of {product.name}",
            "product_id": product_id,
            "product_name": product.name,
            "branch_id": branch_id,
            "branch_name": branch.name,
            "old_quantity": float(old_quantity) if 'old_quantity' in locals() else 0,
            "new_quantity": float(stock.quantity),
            "added_by": current_user.name,
            "role": current_user.role
        }
        
        print(f"Response: {response_data}")
        return response_data
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR in add_stock: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to add stock: {str(e)}")
    
# POST - Initialize branch stock (Modified to allow both admin and sales with restrictions)
@router.post("/initialize/{branch_id}")   # No trailing slash
@router.post("/initialize/{branch_id}/")  # With trailing slash
def initialize_branch_stock(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)  # Changed from require_admin to get_current_user
):
    """Initialize stock for all products in a branch
    
    - Admin: Can initialize stock for any branch
    - Salesman: Can only initialize stock for their own branch (if branch has no stock)
    """
    
    try:
        # Check if branch exists
        branch = db.query(Branch).filter(Branch.id == branch_id).first()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")
        
        # Permission check: Salesman can only initialize their own branch
        if current_user.role == "salesman":
            if not current_user.branch_id:
                raise HTTPException(status_code=400, detail="User not assigned to a branch")
            if current_user.branch_id != branch_id:
                raise HTTPException(status_code=403, detail="Not authorized to initialize stock for this branch")
        
        # Get all active products
        products = db.query(Product).filter(Product.active == True).all()
        
        created_count = 0
        skipped_count = 0
        
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
            else:
                skipped_count += 1
        
        db.commit()
        
        return {
            "message": f"Initialized stock for {created_count} products in branch {branch.name}",
            "branch_id": branch_id,
            "branch_name": branch.name,
            "products_initialized": created_count,
            "products_already_existing": skipped_count,
            "initialized_by": current_user.name,
            "role": current_user.role
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error in initialize_branch_stock: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Optional: Add a new endpoint for adjusting stock (if needed)
@router.put("/adjust/{branch_id}/{product_id}")
def adjust_stock(
    branch_id: int,
    product_id: int,
    new_quantity: float = Query(..., ge=0),
    notes: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Adjust stock to a specific quantity
    
    - Admin: Can adjust stock for any branch
    - Salesman: Can only adjust stock for their own branch
    """
    
    try:
        # Check if branch exists
        branch = db.query(Branch).filter(Branch.id == branch_id).first()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")
        
        # Check if product exists
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Permission check
        if current_user.role == "salesman":
            if not current_user.branch_id:
                raise HTTPException(status_code=400, detail="User not assigned to a branch")
            if current_user.branch_id != branch_id:
                raise HTTPException(status_code=403, detail="Not authorized to adjust stock for this branch")
        
        # Get stock record
        stock = db.query(Stock).filter(
            Stock.branch_id == branch_id,
            Stock.product_id == product_id
        ).first()
        
        if not stock:
            raise HTTPException(status_code=404, detail="Stock record not found")
        
        # Calculate change
        quantity_change = new_quantity - stock.quantity
        
        # Update stock
        stock.quantity = new_quantity
        
        # Record stock movement
        stock_movement = StockMovement(
            branch_id=branch_id,
            product_id=product_id,
            user_id=current_user.id,
            change_qty=quantity_change,
            movement_type="adjustment",
            notes=notes or f"Stock adjusted by {current_user.name} (Role: {current_user.role})"
        )
        db.add(stock_movement)
        
        db.commit()
        db.refresh(stock)
        
        return {
            "success": True,
            "message": f"Adjusted {product.name} stock to {new_quantity} units",
            "product_id": product_id,
            "branch_id": branch_id,
            "old_quantity": float(stock.quantity - quantity_change),
            "new_quantity": float(stock.quantity),
            "change": float(quantity_change),
            "adjusted_by": current_user.name,
            "role": current_user.role
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error in adjust_stock: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))