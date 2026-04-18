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


# POST - Add stock
@router.post("/{branch_id}/{product_id}/add")
@router.post("/{branch_id}/{product_id}/add/")
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
        
        if stock:
            old_quantity = float(stock.quantity)
            new_quantity = float(stock.quantity) + quantity
            stock.quantity = Decimal(str(new_quantity))
            print(f"Updated existing stock: {old_quantity} -> {new_quantity}")
        else:
            old_quantity = 0
            new_quantity = quantity
            stock = Stock(
                branch_id=branch_id,
                product_id=product_id,
                quantity=Decimal(str(quantity)),
                reorder_level=10
            )
            db.add(stock)
            print(f"Created new stock record with quantity: {quantity}")
        
        # Record stock movement with new_quantity
        stock_movement = StockMovement(
            branch_id=branch_id,
            product_id=product_id,
            user_id=current_user.id,
            change_qty=Decimal(str(quantity)),
            new_quantity=Decimal(str(new_quantity)),
            movement_type="add",
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
            "old_quantity": old_quantity,
            "new_quantity": new_quantity,
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


# POST - Initialize branch stock
@router.post("/initialize/{branch_id}")
@router.post("/initialize/{branch_id}/")
def initialize_branch_stock(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
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


# PUT - Adjust stock to a specific quantity
@router.put("/{branch_id}/{product_id}")
def adjust_stock(
    branch_id: int,
    product_id: int,
    quantity: float = Query(..., ge=0),
    reason: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Adjust stock to a specific quantity
    
    - Admin: Can adjust stock for any branch
    - Salesman: Can only adjust stock for their own branch
    """
    
    try:
        print(f"=== ADJUST STOCK DEBUG ===")
        print(f"Branch ID: {branch_id}")
        print(f"Product ID: {product_id}")
        print(f"New Quantity: {quantity}")
        print(f"Reason: {reason}")
        print(f"Current User ID: {current_user.id}")
        print(f"Current User Role: {current_user.role}")
        
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
        old_quantity = float(stock.quantity)
        quantity_change = quantity - old_quantity
        
        # Update stock
        stock.quantity = Decimal(str(quantity))
        new_quantity = float(stock.quantity)
        
        # Record stock movement with new_quantity and reason
        stock_movement = StockMovement(
            branch_id=branch_id,
            product_id=product_id,
            user_id=current_user.id,
            change_qty=Decimal(str(quantity_change)),
            new_quantity=Decimal(str(new_quantity)),
            movement_type="adjustment",
            reason=reason,
            notes=f"Stock adjusted by {current_user.name} (Role: {current_user.role})"
        )
        db.add(stock_movement)
        
        db.commit()
        db.refresh(stock)
        
        return {
            "success": True,
            "message": f"Adjusted {product.name} stock to {quantity} units",
            "product_id": product_id,
            "product_name": product.name,
            "branch_id": branch_id,
            "branch_name": branch.name,
            "old_quantity": old_quantity,
            "new_quantity": new_quantity,
            "change": quantity_change,
            "reason": reason,
            "adjusted_by": current_user.name,
            "role": current_user.role
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"Error in adjust_stock: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# GET - Stock history for a product
@router.get("/{branch_id}/history/{product_id}")
def get_stock_history(
    branch_id: int,
    product_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get stock movement history for a specific product in a branch
    
    - Admin: Can view history for any branch
    - Salesman: Can only view history for their own branch
    """
    
    try:
        print(f"=== STOCK HISTORY DEBUG ===")
        print(f"Branch ID: {branch_id}")
        print(f"Product ID: {product_id}")
        print(f"Limit: {limit}")
        print(f"Current User Role: {current_user.role}")
        
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
                raise HTTPException(status_code=403, detail="Not authorized to view history for this branch")
        
        # Get stock movements for this branch and product
        movements = db.query(StockMovement).filter(
            StockMovement.branch_id == branch_id,
            StockMovement.product_id == product_id
        ).order_by(StockMovement.created_at.desc()).limit(limit).all()
        
        print(f"Found {len(movements)} movement records")
        
        result = []
        for movement in movements:
            # Get user name if available
            user_name = None
            if movement.user_id:
                user = db.query(User).filter(User.id == movement.user_id).first()
                if user:
                    user_name = user.name
            
            # Determine movement type for display
            movement_type_display = movement.movement_type
            if movement_type_display == "add":
                movement_type_display = "add"
            elif movement_type_display == "adjustment":
                movement_type_display = "adjust"
            elif movement_type_display == "purchase":
                movement_type_display = "add"
            
            result.append({
                "id": movement.id,
                "branch_id": movement.branch_id,
                "product_id": movement.product_id,
                "user_id": movement.user_id,
                "user_name": user_name,
                "quantity_change": float(movement.change_qty),
                "new_quantity": float(movement.new_quantity) if movement.new_quantity is not None else None,
                "type": movement_type_display,
                "reason": movement.reason if hasattr(movement, 'reason') else None,
                "notes": movement.notes,
                "created_at": movement.created_at.isoformat() if movement.created_at else None
            })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_stock_history: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))