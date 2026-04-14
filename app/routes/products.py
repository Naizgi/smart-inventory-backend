from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.services import ProductService
from app.schemas import Product, ProductCreate, ProductUpdate
from app.utils.dependencies import get_current_user, require_admin
from app.models import User

router = APIRouter(prefix="/api/products", tags=["Products"])

# ✅ READ operations - Any authenticated user (no admin required)
# GET - Get all products (handle both with and without trailing slash)
@router.get("", response_model=List[Product])   # No slash - /api/products
@router.get("/", response_model=List[Product])  # With slash - /api/products/
def get_products(
    active: Optional[bool] = Query(True),
    branch_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # Changed from require_admin
):
    """Get all products - Any authenticated user"""
    return ProductService.get_products(db, active, branch_id)

# GET by ID - no change needed (already has slash before ID)
@router.get("/{product_id}", response_model=Product)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # Changed from require_admin
):
    """Get product details - Any authenticated user"""
    product = ProductService.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

# ✏️ WRITE operations - Admin only
# POST - Create product (handle both with and without trailing slash)
@router.post("", response_model=Product, status_code=status.HTTP_201_CREATED)   # No slash - /api/products
@router.post("/", response_model=Product, status_code=status.HTTP_201_CREATED)  # With slash - /api/products/
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)  # Kept as admin only
):
    """Create a new product (Admin only)"""
    try:
        return ProductService.create_product(db, product)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# PUT by ID - no change needed
@router.put("/{product_id}", response_model=Product)
def update_product(
    product_id: int,
    product: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)  # Kept as admin only
):
    """Update product (Admin only)"""
    updated_product = ProductService.update_product(db, product_id, product)
    if not updated_product:
        raise HTTPException(status_code=404, detail="Product not found")
    return updated_product

# DELETE by ID - no change needed
@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)  # Kept as admin only
):
    """Delete product (Admin only)"""
    success = ProductService.delete_product(db, product_id)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    return None


# POST - Initialize stock for all existing products
@router.post("/initialize-stock", status_code=status.HTTP_200_OK)
def initialize_stock_for_all_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Initialize stock records for all products in all branches (Admin only)"""
    try:
        # Get all products
        products = ProductService.get_products(db, active=None)
        
        # Get all branches
        branches = db.query(Branch).all()
        
        results = {
            "total_products": len(products),
            "total_branches": len(branches),
            "stock_records_created": 0,
            "stock_records_skipped": 0,
            "errors": []
        }
        
        for product in products:
            for branch in branches:
                try:
                    # Check if stock already exists
                    existing_stock = StockService.get_stock(db, branch.id, product.id)
                    if not existing_stock:
                        # Create stock record with 0 quantity
                        stock = StockService.add_stock(
                            db=db,
                            branch_id=branch.id,
                            product_id=product.id,
                            quantity=0,
                            user_id=current_user.id,
                            notes=f"Bulk initialization: Stock record for product {product.name}"
                        )
                        results["stock_records_created"] += 1
                    else:
                        results["stock_records_skipped"] += 1
                except Exception as e:
                    results["errors"].append({
                        "product_id": product.id,
                        "product_name": product.name,
                        "branch_id": branch.id,
                        "branch_name": branch.name,
                        "error": str(e)
                    })
        
        return {
            "message": "Stock initialization completed",
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize stock: {str(e)}")


# POST - Initialize stock for a single product in all branches
@router.post("/{product_id}/initialize-stock", status_code=status.HTTP_200_OK)
def initialize_stock_for_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Initialize stock records for a specific product in all branches (Admin only)"""
    try:
        # Check if product exists
        product = ProductService.get_product(db, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Get all branches
        branches = db.query(Branch).all()
        
        results = {
            "product_id": product_id,
            "product_name": product.name,
            "total_branches": len(branches),
            "stock_records_created": 0,
            "stock_records_existing": 0,
            "errors": []
        }
        
        for branch in branches:
            try:
                # Check if stock already exists
                existing_stock = StockService.get_stock(db, branch.id, product_id)
                if not existing_stock:
                    # Create stock record with 0 quantity
                    stock = StockService.add_stock(
                        db=db,
                        branch_id=branch.id,
                        product_id=product_id,
                        quantity=0,
                        user_id=current_user.id,
                        notes=f"Initialized stock record for product: {product.name}"
                    )
                    results["stock_records_created"] += 1
                else:
                    results["stock_records_existing"] += 1
            except Exception as e:
                results["errors"].append({
                    "branch_id": branch.id,
                    "branch_name": branch.name,
                    "error": str(e)
                })
        
        return {
            "message": f"Stock initialization completed for product {product.name}",
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize stock: {str(e)}")