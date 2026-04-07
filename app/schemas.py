from enum import Enum
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from datetime import datetime, date
from typing import Optional, List, Any
from decimal import Decimal

# ==================== BRANCH SCHEMAS ====================
class BranchBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=50)

class BranchCreate(BranchBase):
    pass

class BranchUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=50)

class Branch(BranchBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== PRODUCT SCHEMAS ====================
class ProductBase(BaseModel):
    sku: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, max_length=50)
    size: Optional[str] = Field(None, max_length=50)
    pages: Optional[int] = Field(None, ge=0)
    price: float = Field(..., gt=0)
    cost: float = Field(..., gt=0)
    active: bool = True

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    sku: Optional[str] = Field(None, min_length=1, max_length=100)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, max_length=50)
    size: Optional[str] = Field(None, max_length=50)
    pages: Optional[int] = Field(None, ge=0)
    price: Optional[float] = Field(None, gt=0)
    cost: Optional[float] = Field(None, gt=0)
    active: Optional[bool] = None

class Product(ProductBase):
    id: int
    created_at: datetime
    stock_quantity: Optional[float] = 0
    reorder_level: Optional[float] = 0
    
    class Config:
        from_attributes = True


# ==================== USER SCHEMAS ====================
class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    role: str = Field(..., pattern="^(admin|salesman)$")
    branch_id: Optional[int] = None
    active: bool = True

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    role: Optional[str] = Field(None, pattern="^(admin|salesman)$")
    branch_id: Optional[int] = None
    active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6)

class User(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== STOCK SCHEMAS ====================
class StockBase(BaseModel):
    branch_id: int
    product_id: int
    quantity: float = Field(0, ge=0)
    reorder_level: float = Field(0, ge=0)

class StockCreate(StockBase):
    pass

class StockUpdate(BaseModel):
    quantity: Optional[float] = Field(None, ge=0)
    reorder_level: Optional[float] = Field(None, ge=0)

class Stock(StockBase):
    id: int
    
    class Config:
        from_attributes = True

class StockResponse(BaseModel):
    product_id: int
    product_name: str
    product_sku: str
    quantity: float
    reorder_level: float
    status: str  # "normal", "low", "out_of_stock"


# ==================== SALE SCHEMAS ====================
class SaleItemCreate(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)

class SaleItem(BaseModel):
    id: int
    sale_id: int
    product_id: int
    quantity: float
    unit_price: float
    line_total: float
    
    class Config:
        from_attributes = True

class SaleCreate(BaseModel):
    branch_id: Optional[int] = None
    customer_name: Optional[str] = None
    items: List[SaleItemCreate] = Field(..., min_length=1)

class Sale(BaseModel):
    id: int
    branch_id: int
    user_id: int
    customer_name: Optional[str]
    total_amount: float
    total_cost: float
    created_at: datetime
    items: List[SaleItem] = []
    
    class Config:
        from_attributes = True


# ==================== PURCHASE SCHEMAS (Legacy) ====================
class PurchaseItemCreate(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)
    unit_cost: float = Field(..., gt=0)

class PurchaseItem(BaseModel):
    id: int
    purchase_id: int
    product_id: int
    quantity: float
    unit_cost: float
    
    class Config:
        from_attributes = True

class PurchaseCreate(BaseModel):
    branch_id: int
    supplier_name: Optional[str] = None
    items: List[PurchaseItemCreate] = Field(..., min_length=1)

class Purchase(BaseModel):
    id: int
    branch_id: int
    supplier_name: Optional[str]
    total_amount: float
    created_at: datetime
    items: List[PurchaseItem] = []
    
    class Config:
        from_attributes = True


# ==================== ALERT SCHEMAS ====================
class Alert(BaseModel):
    branch_id: int
    product_id: int
    message: str

class AlertResponse(BaseModel):
    id: int
    branch_id: int
    product_id: int
    product_name: Optional[str] = None
    branch_name: Optional[str] = None
    message: str
    created_at: datetime
    resolved: bool
    resolved_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ==================== AUTH SCHEMAS ====================
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    user_id: Optional[int] = None
    branch_id: Optional[int] = None

class LoginRequest(BaseModel):
    username: str
    password: str


# ==================== NEW ENUMS ====================
class PurchaseStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    PARTIALLY_RECEIVED = "partially_received"

class LoanStatus(str, Enum):
    ACTIVE = "active"
    PARTIALLY_PAID = "partially_paid"
    SETTLED = "settled"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

class LoanPaymentMethod(str, Enum):
    CASH = "cash"
    TICKET = "ticket"
    COUPON = "coupon"
    MIXED = "mixed"


# ==================== DATE RANGE SCHEMA ====================
class DateRange(BaseModel):
    from_date: date
    to_date: date


# ==================== TICKET SUMMARY SCHEMA ====================
class TicketSummary(BaseModel):
    total_tickets_purchased: int = 0
    total_tickets_used: int = 0
    total_tickets_remaining: int = 0
    total_revenue_from_tickets: float = 0
    total_purchased_value: float = 0
    ticket_utilization_rate: float = 0


# ==================== PURCHASE ORDER SCHEMAS ====================
class PurchaseOrderItemBase(BaseModel):
    product_id: int
    quantity_ordered: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(gt=0)
    notes: Optional[str] = None

class PurchaseOrderItemCreate(PurchaseOrderItemBase):
    pass

class PurchaseOrderItemResponse(PurchaseOrderItemBase):
    id: int
    quantity_received: Decimal
    total_cost: Decimal
    received_at: Optional[datetime] = None
    product_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class PurchaseOrderBase(BaseModel):
    supplier: str
    expected_delivery_date: Optional[date] = None
    tax_amount: Decimal = Field(default=0, ge=0)
    shipping_cost: Decimal = Field(default=0, ge=0)
    discount_amount: Decimal = Field(default=0, ge=0)
    notes: Optional[str] = None

class PurchaseOrderCreate(PurchaseOrderBase):
    items: List[PurchaseOrderItemCreate]

class PurchaseOrderUpdate(BaseModel):
    status: Optional[PurchaseStatus] = None
    actual_delivery_date: Optional[date] = None
    notes: Optional[str] = None

class PurchaseOrderResponse(PurchaseOrderBase):
    id: int
    order_number: str
    branch_id: int
    order_date: datetime
    actual_delivery_date: Optional[datetime] = None
    status: PurchaseStatus
    subtotal: Decimal
    total_amount: Decimal
    items: List[PurchaseOrderItemResponse]
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class ReceivePurchaseItem(BaseModel):
    product_id: int
    quantity_received: Decimal = Field(gt=0)

class ReceivePurchaseOrder(BaseModel):
    items: List[ReceivePurchaseItem]
    actual_delivery_date: date


# ==================== LOAN SCHEMAS ====================
class LoanItemBase(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(gt=0)

class LoanItemCreate(LoanItemBase):
    pass

class LoanItemResponse(LoanItemBase):
    id: int
    line_total: Decimal
    product_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class LoanBase(BaseModel):
    customer_name: str = Field(min_length=2, max_length=255)
    customer_phone: Optional[str] = None
    customer_email: Optional[EmailStr] = None
    due_date: date
    interest_rate: Decimal = Field(default=0, ge=0, le=100)
    notes: Optional[str] = None

class LoanCreate(LoanBase):
    items: List[LoanItemCreate]

class LoanUpdate(BaseModel):
    due_date: Optional[date] = None
    interest_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    status: Optional[LoanStatus] = None
    notes: Optional[str] = None

class LoanPaymentBase(BaseModel):
    amount: Decimal = Field(gt=0)
    payment_method: LoanPaymentMethod
    reference_number: Optional[str] = None
    notes: Optional[str] = None

class LoanPaymentCreate(LoanPaymentBase):
    sale_id: Optional[int] = None

class LoanPaymentResponse(LoanPaymentBase):
    id: int
    payment_number: str
    payment_date: datetime
    recorded_by: str
    sale_id: Optional[int] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class LoanResponse(LoanBase):
    id: int
    loan_number: str
    branch_id: int
    loan_date: datetime
    total_amount: Decimal
    paid_amount: Decimal
    remaining_amount: Decimal
    interest_amount: Decimal
    status: LoanStatus
    items: List[LoanItemResponse]
    payments: List[LoanPaymentResponse] = []
    created_by: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class LoanSettleRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    payment_method: LoanPaymentMethod
    reference_number: Optional[str] = None
    notes: Optional[str] = None

class LoanSummaryResponse(BaseModel):
    summary_date: date
    branch_id: int
    total_loans_issued: int
    total_loan_amount: Decimal
    total_repayments: Decimal
    total_outstanding: Decimal
    active_loans_count: int
    overdue_loans_count: int
    
    model_config = ConfigDict(from_attributes=True)

class LoanReport(BaseModel):
    date_range: DateRange
    total_loans: int
    total_loan_value: Decimal
    total_repayments: Decimal
    total_outstanding: Decimal
    average_loan_size: Decimal
    repayment_rate: float
    loans_by_status: dict
    daily_breakdown: List[dict]


# ==================== COMBINED SALES REPORT SCHEMA ====================
class CombinedSalesReport(BaseModel):
    date_range: DateRange
    total_sales: float
    total_cash_sales: float
    total_ticket_sales: float
    total_coupons_used: int
    total_tickets_used: int
    total_orders: int
    daily_breakdown: List[dict]
    top_coupon_items: List[dict] = []
    top_ticket_items: List[dict] = []
    ticket_summary: TicketSummary
    loan_summary: Optional[LoanReport] = None
    loan_repayments: float = 0
    
    
# Add these schemas to your schemas.py

class TempItemStatus(str, Enum):
    PENDING = "pending"
    RECEIVED = "received"
    CANCELLED = "cancelled"

class TempItemBase(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    quantity: int = Field(default=1, ge=1)
    unit_price: Optional[float] = Field(None, gt=0)
    customer_name: Optional[str] = Field(None, max_length=255)
    customer_phone: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None

class TempItemCreate(TempItemBase):
    pass

class TempItemUpdate(BaseModel):
    status: Optional[TempItemStatus] = None
    notes: Optional[str] = None

class TempItemResponse(TempItemBase):
    id: int
    item_number: str
    status: TempItemStatus
    registered_by: str
    registered_at: datetime
    received_by: Optional[str] = None
    received_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True    
        
        # ==================== SETTINGS SCHEMAS ====================

class SystemSettingBase(BaseModel):
    category: str = Field(..., min_length=1, max_length=50)
    key: str = Field(..., min_length=1, max_length=100)
    value: Any

class SystemSettingCreate(SystemSettingBase):
    pass

class SystemSettingUpdate(BaseModel):
    value: Any

class SystemSettingResponse(SystemSettingBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class BackupRecordBase(BaseModel):
    name: str
    file_path: str
    size_mb: float = 0

class BackupRecordResponse(BackupRecordBase):
    id: int
    created_by: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SystemLogBase(BaseModel):
    log_type: str
    message: str
    details: Optional[str] = None
    ip_address: Optional[str] = None

class SystemLogResponse(SystemLogBase):
    id: int
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Settings update request models
class GeneralSettingsUpdate(BaseModel):
    system_name: str = Field(default="Inventory System")
    timezone: str = Field(default="Africa/Addis_Ababa")
    date_format: str = Field(default="YYYY-MM-DD")
    currency: str = Field(default="ETB")
    language: str = Field(default="en")

class CouponSettingsUpdate(BaseModel):
    auto_reset: bool = True
    reset_time: str = Field(default="00:00")
    low_stock_alert: bool = True
    alert_threshold: int = Field(default=20, ge=0, le=100)
    default_coupon: int = Field(default=100, ge=0)

class NotificationSettingsUpdate(BaseModel):
    low_stock_email: bool = True
    daily_report_email: bool = True
    sms_alerts: bool = False
    email_recipients: List[str] = []

class BackupSettingsUpdate(BaseModel):
    auto_backup: bool = True
    frequency: str = Field(default="daily", pattern="^(daily|weekly|monthly)$")
    backup_time: str = Field(default="23:00")
    location: str = Field(default="local", pattern="^(local|cloud)$")
    retention_days: int = Field(default=30, ge=1, le=365)


class SystemInfoResponse(BaseModel):
    version: str
    build_date: str
    database: str
    server_status: str
    total_users: int
    total_products: int
    total_branches: int
    recent_sales: int
    uptime_days: int
    last_backup: Optional[str] = None
    cache_size_mb: float
    
    
    
    # Add to schemas.py
class UserProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6)
        