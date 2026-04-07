from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
import traceback

from app.database import get_db
from app.models import User, Sale, SaleItem, Product, Stock, StockMovement, Branch
from app.schemas import Sale as SaleSchema, SaleCreate, SaleItem as SaleItemSchema
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/sales", tags=["Sales"])

@router.post("/", response_model=SaleSchema, status_code=status.HTTP_201_CREATED)
def create_sale(
    sale_data: SaleCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a new sale transaction"""
    
    print(f"=== CREATE SALE ===")
    print(f"User: {current_user.id} - {current_user.name} - Role: {current_user.role}")
    print(f"Sale data: {sale_data}")
    
    try:
        # Determine branch
        branch_id = sale_data.branch_id or current_user.branch_id
        
        if not branch_id:
            raise HTTPException(
                status_code=400, 
                detail="Branch ID is required"
            )
        
        print(f"Branch ID: {branch_id}")
        
        # Check if salesman has access to this branch
        if current_user.role == "salesman" and current_user.branch_id != branch_id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to sell from this branch"
            )
        
        # Check if branch exists
        branch = db.query(Branch).filter(Branch.id == branch_id).first()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")
        
        total_amount = Decimal('0')
        total_cost = Decimal('0')
        sale_items = []
        
        # Process each item
        for idx, item_data in enumerate(sale_data.items):
            print(f"Processing item {idx}: product_id={item_data.product_id}, quantity={item_data.quantity}, price={item_data.unit_price}")
            
            # Get product
            product = db.query(Product).filter(Product.id == item_data.product_id).first()
            if not product:
                raise HTTPException(status_code=404, detail=f"Product {item_data.product_id} not found")
            
            print(f"Product found: {product.name}, cost={product.cost}")
            
            # Convert to Decimal for consistent math
            quantity_decimal = Decimal(str(item_data.quantity))
            unit_price_decimal = Decimal(str(item_data.unit_price))
            product_cost_decimal = Decimal(str(product.cost))
            
            # Check stock
            stock = db.query(Stock).filter(
                Stock.branch_id == branch_id,
                Stock.product_id == item_data.product_id
            ).first()
            
            if not stock:
                print(f"No stock record found for product {item_data.product_id} in branch {branch_id}")
                # Create stock record if it doesn't exist
                stock = Stock(
                    branch_id=branch_id,
                    product_id=item_data.product_id,
                    quantity=Decimal('0'),
                    reorder_level=Decimal('10')
                )
                db.add(stock)
                db.flush()
            
            if stock.quantity < quantity_decimal:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for {product.name}. Available: {float(stock.quantity)}, Requested: {float(quantity_decimal)}"
                )
            
            # Calculate totals
            line_total = quantity_decimal * unit_price_decimal
            line_cost = quantity_decimal * product_cost_decimal
            
            total_amount += line_total
            total_cost += line_cost
            
            # Update stock - use Decimal subtraction
            stock.quantity = stock.quantity - quantity_decimal
            print(f"Stock updated: new quantity = {stock.quantity}")
            
            # Record stock movement
            stock_movement = StockMovement(
                branch_id=branch_id,
                product_id=item_data.product_id,
                user_id=current_user.id,
                change_qty=-quantity_decimal,
                movement_type="sale",
                notes=f"Sale by {current_user.name}"
            )
            db.add(stock_movement)
            
            sale_items.append({
                "product": product,
                "quantity": quantity_decimal,
                "unit_price": unit_price_decimal,
                "line_total": line_total
            })
        
        # Create sale record
        sale = Sale(
            branch_id=branch_id,
            user_id=current_user.id,
            customer_name=sale_data.customer_name,
            total_amount=total_amount,
            total_cost=total_cost
        )
        db.add(sale)
        db.flush()
        
        # Create sale items
        for item in sale_items:
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=item["product"].id,
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                line_total=item["line_total"]
            )
            db.add(sale_item)
        
        db.commit()
        db.refresh(sale)
        
        # Prepare response with items
        response_items = []
        for item in sale_items:
            response_items.append({
                "id": 0,
                "sale_id": sale.id,
                "product_id": item["product"].id,
                "quantity": float(item["quantity"]),
                "unit_price": float(item["unit_price"]),
                "line_total": float(item["line_total"])
            })
        
        print(f"Sale created successfully! ID: {sale.id}, Total: {float(total_amount)}")
        
        return {
            "id": sale.id,
            "branch_id": sale.branch_id,
            "user_id": sale.user_id,
            "customer_name": sale.customer_name,
            "total_amount": float(sale.total_amount),
            "total_cost": float(sale.total_cost),
            "created_at": sale.created_at,
            "items": response_items
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"Error creating sale: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/", response_model=List[SaleSchema])
def get_sales(
    branch_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get sales with filters"""
    
    query = db.query(Sale)
    
    # Apply filters
    if current_user.role == "salesman":
        # Salesman can only see their own branch
        if branch_id and branch_id != current_user.branch_id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to view sales from other branches"
            )
        query = query.filter(Sale.branch_id == current_user.branch_id)
    elif branch_id:
        query = query.filter(Sale.branch_id == branch_id)
    
    if start_date:
        query = query.filter(Sale.created_at >= start_date)
    if end_date:
        query = query.filter(Sale.created_at <= end_date)
    
    sales = query.order_by(Sale.created_at.desc()).limit(limit).all()
    
    # Load items for each sale
    result = []
    for sale in sales:
        items = db.query(SaleItem).filter(SaleItem.sale_id == sale.id).all()
        result.append({
            "id": sale.id,
            "branch_id": sale.branch_id,
            "user_id": sale.user_id,
            "customer_name": sale.customer_name,
            "total_amount": float(sale.total_amount),
            "total_cost": float(sale.total_cost),
            "created_at": sale.created_at,
            "items": [
                {
                    "id": item.id,
                    "sale_id": item.sale_id,
                    "product_id": item.product_id,
                    "quantity": float(item.quantity),
                    "unit_price": float(item.unit_price),
                    "line_total": float(item.line_total)
                }
                for item in items
            ]
        })
    
    return result


@router.get("/{sale_id}", response_model=SaleSchema)
def get_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a single sale by ID"""
    
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    
    # Check permissions
    if current_user.role == "salesman" and sale.branch_id != current_user.branch_id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to view this sale"
        )
    
    items = db.query(SaleItem).filter(SaleItem.sale_id == sale.id).all()
    
    return {
        "id": sale.id,
        "branch_id": sale.branch_id,
        "user_id": sale.user_id,
        "customer_name": sale.customer_name,
        "total_amount": float(sale.total_amount),
        "total_cost": float(sale.total_cost),
        "created_at": sale.created_at,
        "items": [
            {
                "id": item.id,
                "sale_id": item.sale_id,
                "product_id": item.product_id,
                "quantity": float(item.quantity),
                "unit_price": float(item.unit_price),
                "line_total": float(item.line_total)
            }
            for item in items
        ]
    }