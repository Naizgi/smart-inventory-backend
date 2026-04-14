from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
import traceback
import random
import string

from app.database import get_db
from app.models import (
    User, Sale, SaleItem, Product, Stock, StockMovement, Branch, 
    BankAccount, Refund, RefundItem, SystemSetting
)
from app.schemas import (
    SaleResponse, SaleCreate, SaleItemResponse, 
    RefundCreate, RefundResponse, RefundApprove,
    BankAccountResponse
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/sales", tags=["Sales"])

def generate_invoice_number(db: Session) -> str:
    """Generate a unique invoice number"""
    today = datetime.now().strftime("%Y%m%d")
    prefix = f"INV-{today}-"
    
    # Get the last invoice number for today
    last_sale = db.query(Sale).filter(
        Sale.invoice_number.like(f"{prefix}%")
    ).order_by(Sale.id.desc()).first()
    
    if last_sale:
        last_number = int(last_sale.invoice_number.split("-")[-1])
        new_number = last_number + 1
    else:
        new_number = 1
    
    return f"{prefix}{new_number:04d}"

def get_default_tax_rate(db: Session) -> float:
    """Get default tax rate from settings"""
    setting = db.query(SystemSetting).filter(
        SystemSetting.category == "general",
        SystemSetting.key == "default_tax_rate"
    ).first()
    return float(setting.value) if setting else 15.0

# POST - Create sale with enhanced features
@router.post("", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def create_sale(
    sale_data: SaleCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a new sale transaction with tax, payment method, and bank account support"""
    
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
        
        # Validate bank account if payment method is transfer
        if sale_data.payment_method == "transfer":
            if not sale_data.bank_account_id:
                raise HTTPException(
                    status_code=400,
                    detail="Bank account ID is required for transfer payments"
                )
            
            bank_account = db.query(BankAccount).filter(
                BankAccount.id == sale_data.bank_account_id,
                BankAccount.branch_id == branch_id,
                BankAccount.is_active == True
            ).first()
            
            if not bank_account:
                raise HTTPException(
                    status_code=404,
                    detail="Bank account not found or inactive"
                )
        
        # Calculate subtotal from items
        subtotal = Decimal('0')
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
            item_discount = Decimal(str(item_data.discount_amount)) if item_data.discount_amount else Decimal('0')
            
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
            
            # Calculate line total with discount
            line_subtotal = quantity_decimal * unit_price_decimal
            line_total = line_subtotal - item_discount
            line_cost = quantity_decimal * product_cost_decimal
            
            subtotal += line_subtotal
            total_cost += line_cost
            
            # Update stock
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
                "discount_amount": item_discount,
                "line_total": line_total
            })
        
        # Calculate tax and final total
        tax_rate = Decimal(str(sale_data.tax_rate)) / Decimal('100')
        tax_amount = subtotal * tax_rate if sale_data.tax_rate > 0 else Decimal('0')
        
        # Apply global discount
        global_discount = Decimal(str(sale_data.discount_amount))
        if sale_data.discount_type == "percentage":
            global_discount = subtotal * (Decimal(str(sale_data.discount_amount)) / Decimal('100'))
        
        shipping_cost = Decimal(str(sale_data.shipping_cost))
        
        total_amount = subtotal + tax_amount + shipping_cost - global_discount
        
        # Generate invoice number
        invoice_number = generate_invoice_number(db)
        
        # Create sale record
        sale = Sale(
            invoice_number=invoice_number,
            branch_id=branch_id,
            user_id=current_user.id,
            customer_name=sale_data.customer_name,
            customer_phone=sale_data.customer_phone,
            customer_email=sale_data.customer_email,
            subtotal=subtotal,
            tax_amount=tax_amount,
            tax_rate=Decimal(str(sale_data.tax_rate)),
            discount_amount=global_discount,
            discount_type=sale_data.discount_type,
            shipping_cost=shipping_cost,
            total_amount=total_amount,
            total_cost=total_cost,
            payment_method=sale_data.payment_method,
            bank_account_id=sale_data.bank_account_id,
            transaction_reference=sale_data.transaction_reference,
            status="completed",
            refund_amount=Decimal('0'),
            refund_status="none",
            notes=sale_data.notes
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
                discount_amount=item["discount_amount"],
                line_total=item["line_total"]
            )
            db.add(sale_item)
        
        db.commit()
        db.refresh(sale)
        
        # Prepare response
        response_items = []
        for item in sale_items:
            response_items.append({
                "id": 0,
                "sale_id": sale.id,
                "product_id": item["product"].id,
                "product_name": item["product"].name,
                "product_sku": item["product"].sku,
                "quantity": float(item["quantity"]),
                "unit_price": float(item["unit_price"]),
                "discount_amount": float(item["discount_amount"]),
                "line_total": float(item["line_total"])
            })
        
        # Get bank account details if applicable
        bank_account_details = None
        if sale.bank_account_id:
            bank_account = db.query(BankAccount).filter(BankAccount.id == sale.bank_account_id).first()
            if bank_account:
                bank_account_details = {
                    "id": bank_account.id,
                    "bank_name": bank_account.bank_name,
                    "account_number": bank_account.account_number,
                    "account_name": bank_account.account_name
                }
        
        print(f"Sale created successfully! Invoice: {invoice_number}, Total: {float(total_amount)}")
        
        return {
            "id": sale.id,
            "invoice_number": sale.invoice_number,
            "branch_id": sale.branch_id,
            "branch_name": branch.name,
            "user_id": sale.user_id,
            "user_name": current_user.name,
            "customer_name": sale.customer_name,
            "customer_phone": sale.customer_phone,
            "customer_email": sale.customer_email,
            "subtotal": float(sale.subtotal),
            "tax_amount": float(sale.tax_amount),
            "tax_rate": float(sale.tax_rate),
            "discount_amount": float(sale.discount_amount),
            "discount_type": sale.discount_type,
            "shipping_cost": float(sale.shipping_cost),
            "total_amount": float(sale.total_amount),
            "total_cost": float(sale.total_cost),
            "payment_method": sale.payment_method,
            "bank_account_id": sale.bank_account_id,
            "bank_account_details": bank_account_details,
            "transaction_reference": sale.transaction_reference,
            "status": sale.status,
            "refund_amount": float(sale.refund_amount),
            "refund_status": sale.refund_status,
            "created_at": sale.created_at,
            "updated_at": sale.updated_at,
            "notes": sale.notes,
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

# GET - Get all sales with enhanced response
@router.get("", response_model=List[SaleResponse])
@router.get("/", response_model=List[SaleResponse])
def get_sales(
    branch_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    payment_method: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get sales with filters including payment method and status"""
    
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
    if payment_method:
        query = query.filter(Sale.payment_method == payment_method)
    if status:
        query = query.filter(Sale.status == status)
    
    sales = query.order_by(Sale.created_at.desc()).limit(limit).all()
    
    # Load items and bank account details for each sale
    result = []
    for sale in sales:
        items = db.query(SaleItem).filter(SaleItem.sale_id == sale.id).all()
        
        bank_account_details = None
        if sale.bank_account_id:
            bank_account = db.query(BankAccount).filter(BankAccount.id == sale.bank_account_id).first()
            if bank_account:
                bank_account_details = {
                    "id": bank_account.id,
                    "bank_name": bank_account.bank_name,
                    "account_number": bank_account.account_number,
                    "account_name": bank_account.account_name
                }
        
        result.append({
            "id": sale.id,
            "invoice_number": sale.invoice_number,
            "branch_id": sale.branch_id,
            "branch_name": sale.branch.name if sale.branch else None,
            "user_id": sale.user_id,
            "user_name": sale.user.name if sale.user else None,
            "customer_name": sale.customer_name,
            "customer_phone": sale.customer_phone,
            "customer_email": sale.customer_email,
            "subtotal": float(sale.subtotal),
            "tax_amount": float(sale.tax_amount),
            "tax_rate": float(sale.tax_rate),
            "discount_amount": float(sale.discount_amount),
            "discount_type": sale.discount_type,
            "shipping_cost": float(sale.shipping_cost),
            "total_amount": float(sale.total_amount),
            "total_cost": float(sale.total_cost),
            "payment_method": sale.payment_method,
            "bank_account_id": sale.bank_account_id,
            "bank_account_details": bank_account_details,
            "transaction_reference": sale.transaction_reference,
            "status": sale.status,
            "refund_amount": float(sale.refund_amount),
            "refund_status": sale.refund_status,
            "created_at": sale.created_at,
            "updated_at": sale.updated_at,
            "notes": sale.notes,
            "items": [
                {
                    "id": item.id,
                    "sale_id": item.sale_id,
                    "product_id": item.product_id,
                    "product_name": item.product.name if item.product else None,
                    "product_sku": item.product.sku if item.product else None,
                    "quantity": float(item.quantity),
                    "unit_price": float(item.unit_price),
                    "discount_amount": float(item.discount_amount),
                    "line_total": float(item.line_total)
                }
                for item in items
            ]
        })
    
    return result

# GET by ID with enhanced response
@router.get("/{sale_id}", response_model=SaleResponse)
def get_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a single sale by ID with all details"""
    
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
    
    bank_account_details = None
    if sale.bank_account_id:
        bank_account = db.query(BankAccount).filter(BankAccount.id == sale.bank_account_id).first()
        if bank_account:
            bank_account_details = {
                "id": bank_account.id,
                "bank_name": bank_account.bank_name,
                "account_number": bank_account.account_number,
                "account_name": bank_account.account_name
            }
    
    return {
        "id": sale.id,
        "invoice_number": sale.invoice_number,
        "branch_id": sale.branch_id,
        "branch_name": sale.branch.name if sale.branch else None,
        "user_id": sale.user_id,
        "user_name": sale.user.name if sale.user else None,
        "customer_name": sale.customer_name,
        "customer_phone": sale.customer_phone,
        "customer_email": sale.customer_email,
        "subtotal": float(sale.subtotal),
        "tax_amount": float(sale.tax_amount),
        "tax_rate": float(sale.tax_rate),
        "discount_amount": float(sale.discount_amount),
        "discount_type": sale.discount_type,
        "shipping_cost": float(sale.shipping_cost),
        "total_amount": float(sale.total_amount),
        "total_cost": float(sale.total_cost),
        "payment_method": sale.payment_method,
        "bank_account_id": sale.bank_account_id,
        "bank_account_details": bank_account_details,
        "transaction_reference": sale.transaction_reference,
        "status": sale.status,
        "refund_amount": float(sale.refund_amount),
        "refund_status": sale.refund_status,
        "created_at": sale.created_at,
        "updated_at": sale.updated_at,
        "notes": sale.notes,
        "items": [
            {
                "id": item.id,
                "sale_id": item.sale_id,
                "product_id": item.product_id,
                "product_name": item.product.name if item.product else None,
                "product_sku": item.product.sku if item.product else None,
                "quantity": float(item.quantity),
                "unit_price": float(item.unit_price),
                "discount_amount": float(item.discount_amount),
                "line_total": float(item.line_total)
            }
            for item in items
        ]
    }

# Update sale (e.g., add notes, update customer info)
@router.put("/{sale_id}", response_model=SaleResponse)
def update_sale(
    sale_id: int,
    sale_update: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update sale information (customer info, notes, etc.)"""
    
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    
    # Check permissions
    if current_user.role == "salesman" and sale.branch_id != current_user.branch_id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to update this sale"
        )
    
    # Only allow updating certain fields
    allowed_fields = ["customer_name", "customer_phone", "customer_email", "notes"]
    for field in allowed_fields:
        if field in sale_update:
            setattr(sale, field, sale_update[field])
    
    db.commit()
    db.refresh(sale)
    
    return get_sale(sale_id, db, current_user)

# Get sales summary by payment method
@router.get("/summary/payment-methods")
def get_sales_by_payment_method(
    branch_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get sales summary grouped by payment method"""
    
    query = db.query(Sale)
    
    if current_user.role == "salesman":
        query = query.filter(Sale.branch_id == current_user.branch_id)
    elif branch_id:
        query = query.filter(Sale.branch_id == branch_id)
    
    if start_date:
        query = query.filter(Sale.created_at >= start_date)
    if end_date:
        query = query.filter(Sale.created_at <= end_date)
    
    sales = query.all()
    
    # Group by payment method
    summary = {}
    for sale in sales:
        method = sale.payment_method
        if method not in summary:
            summary[method] = {
                "count": 0,
                "total_amount": 0,
                "total_tax": 0
            }
        summary[method]["count"] += 1
        summary[method]["total_amount"] += float(sale.total_amount)
        summary[method]["total_tax"] += float(sale.tax_amount)
    
    return summary

# Get sales summary by status
@router.get("/summary/status")
def get_sales_by_status(
    branch_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get sales summary grouped by status"""
    
    query = db.query(Sale)
    
    if current_user.role == "salesman":
        query = query.filter(Sale.branch_id == current_user.branch_id)
    elif branch_id:
        query = query.filter(Sale.branch_id == branch_id)
    
    if start_date:
        query = query.filter(Sale.created_at >= start_date)
    if end_date:
        query = query.filter(Sale.created_at <= end_date)
    
    sales = query.all()
    
    # Group by status
    summary = {}
    for sale in sales:
        status = sale.status
        if status not in summary:
            summary[status] = {
                "count": 0,
                "total_amount": 0,
                "total_refund": 0
            }
        summary[status]["count"] += 1
        summary[status]["total_amount"] += float(sale.total_amount)
        summary[status]["total_refund"] += float(sale.refund_amount)
    
    return summary