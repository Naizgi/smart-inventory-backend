from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional
from datetime import datetime, timedelta, date
from app.database import get_db
from app.services import ReportService
from app.utils.dependencies import require_admin
from app.models import (
    Purchase, PurchaseOrder, PurchaseOrderItem, Loan, LoanPayment, 
    Sale, SaleItem, Product, Stock, User, Branch, PurchaseItem
)

router = APIRouter(prefix="/api/reports", tags=["Reports"])

# GET - Sales report (handle both with and without trailing slash)
@router.get("/sales")   # No slash - /api/reports/sales
@router.get("/sales/")  # With slash - /api/reports/sales/
def sales_report(
    report_type: str = Query(..., regex="^(weekly|monthly)$"),
    branch_id: Optional[int] = None,
    include_loan_repayments: bool = Query(True, description="Include loan repayments in revenue"),
    include_purchases: bool = Query(True, description="Include purchase costs for profit calculation"),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Generate sales report with purchases and loan repayments (Admin only)"""
    try:
        # Calculate date ranges based on report type
        end_date = date.today()
        
        if report_type == "weekly":
            start_date = end_date - timedelta(days=7)
        else:  # monthly
            start_date = end_date - timedelta(days=30)
        
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        # Base query for sales
        sales_query = db.query(Sale).filter(
            Sale.created_at.between(start_datetime, end_datetime)
        )
        
        if branch_id:
            sales_query = sales_query.filter(Sale.branch_id == branch_id)
        
        sales = sales_query.all()
        
        # Calculate sales metrics
        total_sales = len(sales)
        total_revenue = sum(sale.total_amount for sale in sales)
        average_sale_value = total_revenue / total_sales if total_sales > 0 else 0
        
        # Calculate profit (assuming profit margin is stored or calculated)
        total_profit = 0
        for sale in sales:
            for item in sale.items:
                # Get the product's cost price
                product = item.product
                cost_per_unit = product.cost if hasattr(product, 'cost') else 0
                profit_per_item = (item.unit_price - cost_per_unit) * item.quantity
                total_profit += profit_per_item
        
        # Get best selling products
        best_selling = db.query(
            Product.id,
            Product.name,
            Product.sku,
            func.sum(SaleItem.quantity).label('total_quantity'),
            func.sum(SaleItem.quantity * SaleItem.unit_price).label('total_revenue')
        ).join(
            SaleItem, Product.id == SaleItem.product_id
        ).join(
            Sale, SaleItem.sale_id == Sale.id
        ).filter(
            Sale.created_at.between(start_datetime, end_datetime)
        )
        
        if branch_id:
            best_selling = best_selling.filter(Sale.branch_id == branch_id)
        
        best_selling = best_selling.group_by(Product.id).order_by(
            func.sum(SaleItem.quantity).desc()
        ).limit(10).all()
        
        # Get slow moving products (products with low sales volume)
        slow_moving = db.query(
            Product.id,
            Product.name,
            Product.sku,
            func.coalesce(func.sum(SaleItem.quantity), 0).label('total_quantity'),
            func.coalesce(func.sum(SaleItem.quantity * SaleItem.unit_price), 0).label('total_revenue')
        ).outerjoin(
            SaleItem, Product.id == SaleItem.product_id
        ).outerjoin(
            Sale, and_(
                SaleItem.sale_id == Sale.id,
                Sale.created_at.between(start_datetime, end_datetime)
            )
        )
        
        if branch_id:
            slow_moving = slow_moving.filter(Sale.branch_id == branch_id)
        
        slow_moving = slow_moving.group_by(Product.id).having(
            func.coalesce(func.sum(SaleItem.quantity), 0) < 5
        ).order_by(
            func.coalesce(func.sum(SaleItem.quantity), 0).asc()
        ).limit(10).all()
        
        # Get loan repayments if requested
        loan_repayments_total = 0
        if include_loan_repayments:
            loan_payments = db.query(LoanPayment).filter(
                LoanPayment.payment_date.between(start_datetime, end_datetime)
            ).all()
            loan_repayments_total = sum(payment.amount for payment in loan_payments)
        
        # Get purchase costs if requested
        purchase_costs_total = 0
        if include_purchases:
            purchase_orders = db.query(PurchaseOrder).filter(
                PurchaseOrder.order_date.between(start_datetime, end_datetime),
                PurchaseOrder.status == 'completed'
            ).all()
            purchase_costs_total = sum(po.total_amount for po in purchase_orders)
        
        return {
            "report_type": report_type,
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "summary": {
                "total_sales": total_sales,
                "total_revenue": float(total_revenue),
                "average_sale_value": float(average_sale_value),
                "total_profit": float(total_profit),
                "profit_margin": float((total_profit / total_revenue * 100) if total_revenue > 0 else 0),
                "loan_repayments": float(loan_repayments_total),
                "purchase_costs": float(purchase_costs_total),
                "net_income": float(total_revenue + loan_repayments_total - purchase_costs_total)
            },
            "best_selling_products": [
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "product_sku": product.sku,
                    "quantity_sold": int(product.total_quantity),
                    "revenue": float(product.total_revenue)
                }
                for product in best_selling
            ],
            "slow_moving_products": [
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "product_sku": product.sku,
                    "quantity_sold": int(product.total_quantity),
                    "revenue": float(product.total_revenue)
                }
                for product in slow_moving
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# GET - Purchase report (handle both with and without trailing slash)
@router.get("/purchases")   # No slash - /api/reports/purchases
@router.get("/purchases/")  # With slash - /api/reports/purchases/
def purchase_report(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    supplier: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Generate purchase report"""
    try:
        # Set default dates (last 30 days if not specified)
        if not to_date:
            to_date = date.today()
        if not from_date:
            from_date = to_date - timedelta(days=30)
        
        start_date = datetime.combine(from_date, datetime.min.time())
        end_date = datetime.combine(to_date, datetime.max.time())
        
        # Get purchase orders
        query = db.query(PurchaseOrder).filter(
            PurchaseOrder.order_date.between(start_date, end_date)
        )
        
        if supplier:
            query = query.filter(PurchaseOrder.supplier.ilike(f"%{supplier}%"))
        
        purchase_orders = query.all()
        
        # Get legacy purchases
        purchases = db.query(Purchase).filter(
            Purchase.created_at.between(start_date, end_date)
        )
        
        if supplier:
            purchases = purchases.filter(Purchase.supplier_name.ilike(f"%{supplier}%"))
        
        purchases_list = purchases.all()
        
        # Calculate totals
        total_purchase_cost = sum(po.total_amount for po in purchase_orders)
        total_legacy_cost = sum(p.total_amount for p in purchases_list)
        
        # Group by supplier
        supplier_totals = {}
        for po in purchase_orders:
            supplier_totals[po.supplier] = supplier_totals.get(po.supplier, 0) + po.total_amount
        
        for p in purchases_list:
            if p.supplier_name:
                supplier_totals[p.supplier_name] = supplier_totals.get(p.supplier_name, 0) + p.total_amount
        
        # Get top purchased products
        top_items = db.query(
            PurchaseOrderItem.product_id,
            Product.name,
            func.sum(PurchaseOrderItem.quantity_received).label('total_quantity'),
            func.sum(PurchaseOrderItem.total_cost).label('total_cost')
        ).join(
            Product, PurchaseOrderItem.product_id == Product.id
        ).join(
            PurchaseOrder, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id
        ).filter(
            PurchaseOrder.order_date.between(start_date, end_date),
            PurchaseOrder.status == 'completed'
        ).group_by(
            PurchaseOrderItem.product_id, Product.name
        ).order_by(
            func.sum(PurchaseOrderItem.total_cost).desc()
        ).limit(10).all()
        
        return {
            "date_range": {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat()
            },
            "summary": {
                "total_purchase_orders": len(purchase_orders),
                "total_purchase_cost": float(total_purchase_cost),
                "total_legacy_purchases": len(purchases_list),
                "total_legacy_cost": float(total_legacy_cost),
                "total_all_purchases": float(total_purchase_cost + total_legacy_cost),
                "average_order_value": float(total_purchase_cost / len(purchase_orders)) if purchase_orders else 0
            },
            "supplier_breakdown": [
                {"supplier": supplier, "total_amount": float(amount)}
                for supplier, amount in sorted(supplier_totals.items(), key=lambda x: x[1], reverse=True)
            ],
            "top_items": [
                {
                    "product_id": item.product_id,
                    "product_name": item.name,
                    "quantity": float(item.total_quantity),
                    "total_cost": float(item.total_cost),
                    "average_cost": float(item.total_cost / item.total_quantity) if item.total_quantity > 0 else 0
                }
                for item in top_items
            ],
            "purchase_orders": [
                {
                    "order_number": po.order_number,
                    "supplier": po.supplier,
                    "order_date": po.order_date.isoformat(),
                    "total_amount": float(po.total_amount),
                    "status": po.status,
                    "items_count": len(po.items)
                }
                for po in purchase_orders[:20]
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# GET - Loan report (handle both with and without trailing slash)
@router.get("/loans")   # No slash - /api/reports/loans
@router.get("/loans/")  # With slash - /api/reports/loans/
def loan_report(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    customer_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Generate loan report"""
    try:
        # Set default dates
        if not to_date:
            to_date = date.today()
        if not from_date:
            from_date = to_date - timedelta(days=30)
        
        start_date = datetime.combine(from_date, datetime.min.time())
        end_date = datetime.combine(to_date, datetime.max.time())
        
        # Get loans created in period
        query = db.query(Loan).filter(
            Loan.created_at.between(start_date, end_date)
        )
        
        if status:
            query = query.filter(Loan.status == status)
        if customer_name:
            query = query.filter(Loan.customer_name.ilike(f"%{customer_name}%"))
        
        loans = query.all()
        
        # Get payments in period
        payments = db.query(LoanPayment).filter(
            LoanPayment.payment_date.between(start_date, end_date)
        ).all()
        
        # Calculate totals
        total_loans_amount = sum(loan.total_amount for loan in loans)
        total_payments = sum(payment.amount for payment in payments)
        
        # Get overdue loans
        now = datetime.now()
        overdue_loans = db.query(Loan).filter(
            Loan.due_date < now,
            Loan.remaining_amount > 0,
            Loan.status != 'settled'
        ).all()
        
        # Payment method breakdown
        payment_methods = {}
        for payment in payments:
            method = payment.payment_method.value if hasattr(payment.payment_method, 'value') else payment.payment_method
            payment_methods[method] = payment_methods.get(method, 0) + payment.amount
        
        return {
            "date_range": {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat()
            },
            "summary": {
                "total_loans_issued": len(loans),
                "total_loan_amount": float(total_loans_amount),
                "total_repayments": float(total_payments),
                "net_outstanding_change": float(total_loans_amount - total_payments),
                "total_outstanding_loans": db.query(Loan).filter(
                    Loan.remaining_amount > 0,
                    Loan.status != 'settled'
                ).count(),
                "total_outstanding_amount": float(db.query(func.sum(Loan.remaining_amount)).filter(
                    Loan.remaining_amount > 0,
                    Loan.status != 'settled'
                ).scalar() or 0),
                "overdue_loans_count": len(overdue_loans),
                "overdue_amount": float(sum(loan.remaining_amount for loan in overdue_loans)),
                "repayment_rate": float((total_payments / total_loans_amount * 100)) if total_loans_amount > 0 else 0
            },
            "payment_method_breakdown": [
                {"method": method, "amount": float(amount)}
                for method, amount in payment_methods.items()
            ],
            "loans_by_status": {
                "active": db.query(Loan).filter(Loan.status == 'active').count(),
                "partially_paid": db.query(Loan).filter(Loan.status == 'partially_paid').count(),
                "settled": db.query(Loan).filter(Loan.status == 'settled').count(),
                "overdue": len(overdue_loans),
                "cancelled": db.query(Loan).filter(Loan.status == 'cancelled').count()
            },
            "recent_loans": [
                {
                    "loan_number": loan.loan_number,
                    "customer_name": loan.customer_name,
                    "total_amount": float(loan.total_amount),
                    "paid_amount": float(loan.paid_amount),
                    "remaining_amount": float(loan.remaining_amount),
                    "due_date": loan.due_date.isoformat(),
                    "status": loan.status,
                    "days_overdue": max(0, (now - loan.due_date).days) if loan.remaining_amount > 0 else 0
                }
                for loan in loans[:20]
            ],
            "overdue_loans": [
                {
                    "loan_number": loan.loan_number,
                    "customer_name": loan.customer_name,
                    "remaining_amount": float(loan.remaining_amount),
                    "due_date": loan.due_date.isoformat(),
                    "days_overdue": (now - loan.due_date).days
                }
                for loan in overdue_loans[:20]
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# GET - Profit/Loss report (handle both with and without trailing slash)
@router.get("/profit-loss")   # No slash - /api/reports/profit-loss
@router.get("/profit-loss/")  # With slash - /api/reports/profit-loss/
def profit_loss_report(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Generate Profit & Loss statement including sales, purchases, and loan repayments"""
    try:
        # Set default dates
        if not to_date:
            to_date = date.today()
        if not from_date:
            from_date = to_date - timedelta(days=30)
        
        start_date = datetime.combine(from_date, datetime.min.time())
        end_date = datetime.combine(to_date, datetime.max.time())
        
        # === REVENUE ===
        # Sales revenue
        sales = db.query(Sale).filter(
            Sale.created_at.between(start_date, end_date)
        ).all()
        
        sales_revenue = sum(sale.total_amount for sale in sales)
        
        # Loan repayments revenue
        loan_payments = db.query(LoanPayment).filter(
            LoanPayment.payment_date.between(start_date, end_date)
        ).all()
        loan_repayment_revenue = sum(payment.amount for payment in loan_payments)
        
        total_revenue = sales_revenue + loan_repayment_revenue
        
        # === COST OF GOODS SOLD ===
        # Purchase costs
        purchase_orders = db.query(PurchaseOrder).filter(
            PurchaseOrder.order_date.between(start_date, end_date),
            PurchaseOrder.status == 'completed'
        ).all()
        purchase_cost = sum(po.total_amount for po in purchase_orders)
        
        legacy_purchases = db.query(Purchase).filter(
            Purchase.created_at.between(start_date, end_date)
        ).all()
        legacy_purchase_cost = sum(p.total_amount for p in legacy_purchases)
        
        total_cogs = purchase_cost + legacy_purchase_cost
        
        # === PROFIT CALCULATIONS ===
        gross_profit = total_revenue - total_cogs
        gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        # === DAILY BREAKDOWN ===
        daily_breakdown = []
        current_date = from_date
        while current_date <= to_date:
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = datetime.combine(current_date, datetime.max.time())
            
            day_sales = db.query(Sale).filter(
                Sale.created_at.between(day_start, day_end)
            ).all()
            
            day_loan_payments = db.query(LoanPayment).filter(
                LoanPayment.payment_date.between(day_start, day_end)
            ).all()
            
            day_purchases = db.query(Purchase).filter(
                Purchase.created_at.between(day_start, day_end)
            ).all()
            
            day_sales_revenue = sum(s.total_amount for s in day_sales)
            day_loan_revenue = sum(p.amount for p in day_loan_payments)
            day_purchase_cost = sum(p.total_amount for p in day_purchases)
            
            daily_breakdown.append({
                "date": current_date.isoformat(),
                "sales_revenue": float(day_sales_revenue),
                "loan_repayments": float(day_loan_revenue),
                "total_revenue": float(day_sales_revenue + day_loan_revenue),
                "purchase_cost": float(day_purchase_cost),
                "gross_profit": float((day_sales_revenue + day_loan_revenue) - day_purchase_cost),
                "transactions_count": len(day_sales)
            })
            
            current_date += timedelta(days=1)
        
        return {
            "date_range": {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat()
            },
            "revenue": {
                "sales_revenue": float(sales_revenue),
                "loan_repayments": float(loan_repayment_revenue),
                "total_revenue": float(total_revenue)
            },
            "cost_of_goods_sold": {
                "purchase_orders": float(purchase_cost),
                "legacy_purchases": float(legacy_purchase_cost),
                "total_cogs": float(total_cogs)
            },
            "profit": {
                "gross_profit": float(gross_profit),
                "gross_margin_percentage": float(gross_margin)
            },
            "summary": {
                "total_sales_transactions": len(sales),
                "total_loan_payments": len(loan_payments),
                "total_purchases": len(purchase_orders) + len(legacy_purchases),
                "average_transaction_value": float(sales_revenue / len(sales)) if sales else 0,
                "average_loan_payment": float(loan_repayment_revenue / len(loan_payments)) if loan_payments else 0
            },
            "daily_breakdown": daily_breakdown
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# GET - Inventory valuation report (handle both with and without trailing slash)
@router.get("/inventory-valuation")   # No slash
@router.get("/inventory-valuation/")  # With slash
def inventory_valuation_report(
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get current inventory valuation based on purchase costs"""
    try:
        inventory_items = db.query(Stock).join(Product).all()
        
        total_value = 0
        items_detail = []
        
        for stock in inventory_items:
            # Get latest purchase cost for this product
            latest_purchase = db.query(PurchaseItem).filter(
                PurchaseItem.product_id == stock.product_id
            ).order_by(Purchase.created_at.desc()).join(Purchase).first()
            
            unit_cost = latest_purchase.unit_cost if latest_purchase else stock.product.cost
            item_value = stock.quantity * unit_cost
            total_value += item_value
            
            items_detail.append({
                "product_id": stock.product_id,
                "product_name": stock.product.name,
                "sku": stock.product.sku,
                "quantity": float(stock.quantity),
                "unit_cost": float(unit_cost),
                "total_value": float(item_value),
                "reorder_level": float(stock.reorder_level),
                "status": "Low Stock" if stock.quantity <= stock.reorder_level else "OK"
            })
        
        return {
            "total_inventory_value": float(total_value),
            "total_products_count": len(inventory_items),
            "low_stock_items": [item for item in items_detail if item["status"] == "Low Stock"],
            "items": items_detail
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# GET - Dashboard summary (handle both with and without trailing slash)
@router.get("/dashboard-summary")   # No slash
@router.get("/dashboard-summary/")  # With slash
def dashboard_summary(
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get quick dashboard summary for today"""
    try:
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end = datetime.combine(date.today(), datetime.max.time())
        
        # Today's sales
        today_sales = db.query(Sale).filter(
            Sale.created_at.between(today_start, today_end)
        ).all()
        
        today_sales_revenue = sum(s.total_amount for s in today_sales)
        today_sales_count = len(today_sales)
        
        # Today's loan repayments
        today_loan_payments = db.query(LoanPayment).filter(
            LoanPayment.payment_date.between(today_start, today_end)
        ).all()
        today_loan_repayments = sum(p.amount for p in today_loan_payments)
        
        # Today's purchases
        today_purchases = db.query(Purchase).filter(
            Purchase.created_at.between(today_start, today_end)
        ).all()
        today_purchase_cost = sum(p.total_amount for p in today_purchases)
        
        # Active loans
        active_loans = db.query(Loan).filter(
            Loan.status.in_(['active', 'partially_paid'])
        ).all()
        
        # Overdue loans
        now = datetime.now()
        overdue_loans = db.query(Loan).filter(
            Loan.due_date < now,
            Loan.remaining_amount > 0,
            Loan.status != 'settled'
        ).all()
        
        # Low stock items
        low_stock_items = db.query(Stock).filter(
            Stock.quantity <= Stock.reorder_level
        ).count()
        
        return {
            "today": {
                "sales_revenue": float(today_sales_revenue),
                "sales_count": today_sales_count,
                "loan_repayments": float(today_loan_repayments),
                "purchase_cost": float(today_purchase_cost),
                "total_income": float(today_sales_revenue + today_loan_repayments),
                "net_cash_flow": float((today_sales_revenue + today_loan_repayments) - today_purchase_cost),
                "average_transaction": float(today_sales_revenue / today_sales_count) if today_sales_count > 0 else 0
            },
            "current_status": {
                "active_loans_count": len(active_loans),
                "active_loans_value": float(sum(loan.remaining_amount for loan in active_loans)),
                "overdue_loans_count": len(overdue_loans),
                "overdue_loans_value": float(sum(loan.remaining_amount for loan in overdue_loans)),
                "low_stock_items_count": low_stock_items
            },
            "quick_actions": [
                "Check overdue loans",
                "Review low stock items",
                "Generate weekly report"
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# GET - Financial summary (handle both with and without trailing slash)
@router.get("/financial-summary")   # No slash
@router.get("/financial-summary/")  # With slash
async def get_financial_summary(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get financial summary for the period"""
    
    start_date = datetime.combine(from_date, datetime.min.time()) if from_date else None
    end_date = datetime.combine(to_date, datetime.max.time()) if to_date else None
    
    query = db.query(Sale)
    if start_date:
        query = query.filter(Sale.created_at >= start_date)
    if end_date:
        query = query.filter(Sale.created_at <= end_date)
    
    sales = query.all()
    total_revenue = sum(s.total_amount for s in sales)
    
    # Get purchase costs (expenses)
    purchase_query = db.query(Purchase)
    if start_date:
        purchase_query = purchase_query.filter(Purchase.created_at >= start_date)
    if end_date:
        purchase_query = purchase_query.filter(Purchase.created_at <= end_date)
    purchases = purchase_query.all()
    total_expenses = sum(p.total_amount for p in purchases)
    
    # Get loan repayments
    loan_payment_query = db.query(LoanPayment)
    if start_date:
        loan_payment_query = loan_payment_query.filter(LoanPayment.payment_date >= start_date)
    if end_date:
        loan_payment_query = loan_payment_query.filter(LoanPayment.payment_date <= end_date)
    loan_payments = loan_payment_query.all()
    loan_repayments = sum(p.amount for p in loan_payments)
    
    # Get outstanding loans
    outstanding_loans = db.query(func.sum(Loan.remaining_amount)).filter(
        Loan.remaining_amount > 0
    ).scalar() or 0
    
    net_profit = total_revenue - total_expenses
    profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    return {
        "total_revenue": float(total_revenue),
        "net_profit": float(net_profit),
        "total_expenses": float(total_expenses),
        "loan_repayments": float(loan_repayments),
        "outstanding_loans": float(outstanding_loans),
        "profit_margin": round(profit_margin, 2),
        "revenue_trend": 12.5  # You can calculate this by comparing with previous period
    }

# GET - Comparison report (handle both with and without trailing slash)
@router.get("/comparison")   # No slash
@router.get("/comparison/")  # With slash
async def get_comparison(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get period comparison data"""
    
    # Get total sales for the period
    start_date = datetime.combine(from_date, datetime.min.time()) if from_date else None
    end_date = datetime.combine(to_date, datetime.max.time()) if to_date else None
    
    query = db.query(Sale)
    if start_date:
        query = query.filter(Sale.created_at >= start_date)
    if end_date:
        query = query.filter(Sale.created_at <= end_date)
    sales = query.all()
    
    total_revenue = sum(s.total_amount for s in sales)
    days = (to_date - from_date).days if from_date and to_date else 30
    
    daily_average = total_revenue / max(days, 1)
    weekly_average = daily_average * 7
    monthly_average = daily_average * 30
    
    return {
        "daily_average": float(daily_average),
        "weekly_average": float(weekly_average),
        "monthly_average": float(monthly_average),
        "total_transactions": len(sales)
    }

# GET - Daily revenue report (handle both with and without trailing slash)
@router.get("/daily-revenue")   # No slash
@router.get("/daily-revenue/")  # With slash
async def get_daily_revenue(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get daily revenue for the last 7 days"""
    
    end_date = to_date if to_date else date.today()
    start_date = from_date if from_date else end_date - timedelta(days=7)
    
    results = []
    current = start_date
    while current <= end_date:
        day_start = datetime.combine(current, datetime.min.time())
        day_end = datetime.combine(current, datetime.max.time())
        
        revenue = db.query(func.sum(Sale.total_amount)).filter(
            Sale.created_at.between(day_start, day_end)
        ).scalar() or 0
        
        results.append({
            "date": current.isoformat(),
            "revenue": float(revenue)
        })
        current += timedelta(days=1)
    
    return results

# GET - Top products report (handle both with and without trailing slash)
@router.get("/top-products")   # No slash
@router.get("/top-products/")  # With slash
async def get_top_products(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    limit: int = Query(5),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get top selling products"""
    
    start_date = datetime.combine(from_date, datetime.min.time()) if from_date else None
    end_date = datetime.combine(to_date, datetime.max.time()) if to_date else None
    
    query = db.query(
        Product.id,
        Product.name,
        func.sum(SaleItem.quantity).label('total_quantity')
    ).join(
        SaleItem, Product.id == SaleItem.product_id
    ).join(
        Sale, SaleItem.sale_id == Sale.id
    )
    
    if start_date:
        query = query.filter(Sale.created_at >= start_date)
    if end_date:
        query = query.filter(Sale.created_at <= end_date)
    
    top_products = query.group_by(Product.id).order_by(
        func.sum(SaleItem.quantity).desc()
    ).limit(limit).all()
    
    return [
        {
            "id": p.id,
            "name": p.name,
            "quantity": int(p.total_quantity)
        }
        for p in top_products
    ]