from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from app.config import settings
from app.models import (
    User, Branch, Product, Stock, Sale, SaleItem, 
    Purchase, PurchaseItem, StockMovement, Alert,
    SystemSetting, BackupRecord, SystemLog, Loan
)
from app.schemas import (
    UserCreate, SaleCreate, PurchaseCreate, StockCreate
)
import json
import os
import bcrypt
import secrets
import random
import string

# Password context for hashing - with fallback handling
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

# In-memory storage for OTPs (use Redis in production)
# Structure: {email: {'otp': '123456', 'expires_at': datetime, 'attempts': 0, 'last_request_at': datetime}}
otp_storage = {}
password_reset_tokens = {}  # {reset_token: {'email': email, 'expires_at': datetime}}

# ==================== AUTH SERVICE ====================
class AuthService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hashed password"""
        try:
            # Bcrypt has a 72-byte limit - truncate if needed
            if len(plain_password) > 72:
                plain_password = plain_password[:72]
            
            # Try passlib first
            return pwd_context.verify(plain_password, hashed_password)
            
        except Exception as e:
            print(f"❌ Passlib verification failed: {e}")
            # Fallback to direct bcrypt
            try:
                return bcrypt.checkpw(
                    plain_password.encode('utf-8'),
                    hashed_password.encode('utf-8')
                )
            except Exception as be:
                print(f"❌ Bcrypt fallback also failed: {be}")
                return False
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password using bcrypt"""
        try:
            # Bcrypt has a 72-byte limit - truncate if needed
            if len(password) > 72:
                password = password[:72]
            
            # Try passlib first
            return pwd_context.hash(password)
            
        except Exception as e:
            print(f"❌ Passlib hash failed: {e}")
            # Fallback to direct bcrypt
            try:
                salt = bcrypt.gensalt()
                return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
            except Exception as be:
                print(f"❌ Bcrypt fallback also failed: {be}")
                raise
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        
        if not AuthService.verify_password(password, user.password_hash):
            return None
        
        if not user.active:
            return None
            
        return user
    
    @staticmethod
    def get_current_user(db: Session, token: str) -> Optional[User]:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id: int = payload.get("user_id")
            if user_id is None:
                return None
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.active:
                return None
            return user
        except JWTError as e:
            print("❌ JWT decode error:", e)
            return None
    
    # ==================== PASSWORD RESET METHODS ====================
    
    @staticmethod
    def generate_otp() -> str:
        """Generate a 6-digit OTP"""
        return ''.join(random.choices(string.digits, k=6))
    
    @staticmethod
    def generate_reset_token() -> str:
        """Generate a secure reset token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def is_admin_email(db: Session, email: str) -> bool:
        """Check if the email belongs to an admin user"""
        user = db.query(User).filter(
            User.email == email,
            User.role == 'admin'
        ).first()
        return user is not None and user.active
    
    @staticmethod
    def send_otp_email(email: str, otp: str):
        """Send OTP to email - Implement with your email service"""
        # For development, just print/log the OTP
        print(f"[DEV] OTP for {email}: {otp}")
        
        # TODO: Uncomment and configure for production email sending
        # Production email sending is commented out to avoid syntax errors
        # When ready to use email, uncomment the code below and configure SMTP settings
        """
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        try:
            msg = MIMEMultipart()
            msg['From'] = settings.SMTP_FROM_EMAIL
            msg['To'] = email
            msg['Subject'] = "Password Reset OTP - Inventory System"
            
            # Simple HTML body
            html_body = f'''
            <html>
            <body style="font-family: Arial, sans-serif;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2FB8A6;">Password Reset Request</h2>
                    <p>You requested to reset your password. Use the following OTP to proceed:</p>
                    <div style="background-color: #f4f4f4; padding: 15px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 5px; margin: 20px 0;">
                        {otp}
                    </div>
                    <p>This OTP is valid for <strong>10 minutes</strong>.</p>
                    <p>If you didn't request this, please ignore this email.</p>
                    <hr>
                    <p style="color: #666; font-size: 12px;">Inventory System - Secure Password Recovery</p>
                </div>
            </body>
            </html>
            '''
            
            msg.attach(MIMEText(html_body, 'html'))
            
            with smtplib.SMTP(settings.SMTP_HOST, int(settings.SMTP_PORT)) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            print(f"Email sent successfully to {email}")
        except Exception as e:
            print(f"Failed to send email to {email}: {e}")
            print(f"OTP for {email}: {otp}")
        """
        
        return True
    
    @staticmethod
    def request_password_reset(db: Session, email: str) -> Dict[str, Any]:
        """Request password reset - sends OTP to admin email"""
        # Check if email exists and is admin
        if not AuthService.is_admin_email(db, email):
            return {
                "success": False,
                "message": "Email not found or not authorized for password reset"
            }
        
        # Generate OTP
        otp = AuthService.generate_otp()
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        
        # Store OTP
        otp_storage[email] = {
            'otp': otp,
            'expires_at': expires_at,
            'attempts': 0
        }
        
        # Send OTP via email
        AuthService.send_otp_email(email, otp)
        
        return {
            "success": True,
            "message": "OTP has been sent to your email address"
        }
    
    @staticmethod
    def verify_otp(db: Session, email: str, otp: str) -> Dict[str, Any]:
        """Verify OTP and return reset token"""
        # Check if email exists in OTP storage
        if email not in otp_storage:
            return {
                "success": False,
                "message": "No OTP request found for this email",
                "resetToken": None
            }
        
        stored_data = otp_storage[email]
        
        # Check if OTP is expired
        if datetime.utcnow() > stored_data['expires_at']:
            # Clean up expired OTP
            del otp_storage[email]
            return {
                "success": False,
                "message": "OTP has expired. Please request a new one.",
                "resetToken": None
            }
        
        # Check attempts (max 5 attempts)
        if stored_data['attempts'] >= 5:
            del otp_storage[email]
            return {
                "success": False,
                "message": "Too many failed attempts. Please request a new OTP.",
                "resetToken": None
            }
        
        # Verify OTP
        if stored_data['otp'] != otp:
            stored_data['attempts'] += 1
            remaining_attempts = 5 - stored_data['attempts']
            return {
                "success": False,
                "message": f"Invalid OTP. {remaining_attempts} attempts remaining.",
                "resetToken": None
            }
        
        # Generate reset token
        reset_token = AuthService.generate_reset_token()
        password_reset_tokens[reset_token] = {
            'email': email,
            'expires_at': datetime.utcnow() + timedelta(minutes=30)
        }
        
        # Clean up OTP
        del otp_storage[email]
        
        return {
            "success": True,
            "message": "OTP verified successfully",
            "resetToken": reset_token
        }
    
    @staticmethod
    def resend_otp(db: Session, email: str) -> Dict[str, Any]:
        """Resend OTP to email"""
        # Check if email exists and is admin
        if not AuthService.is_admin_email(db, email):
            return {
                "success": False,
                "message": "Email not found or not authorized"
            }
        
        # Check for rate limiting (prevent spam)
        if email in otp_storage:
            last_request = otp_storage[email].get('last_request_at')
            if last_request:
                time_since_last = datetime.utcnow() - last_request
                if time_since_last < timedelta(seconds=60):
                    remaining = 60 - time_since_last.seconds
                    return {
                        "success": False,
                        "message": f"Please wait {remaining} seconds before requesting another OTP"
                    }
        
        # Generate new OTP
        otp = AuthService.generate_otp()
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        
        # Update storage
        otp_storage[email] = {
            'otp': otp,
            'expires_at': expires_at,
            'attempts': 0,
            'last_request_at': datetime.utcnow()
        }
        
        # Send OTP via email
        AuthService.send_otp_email(email, otp)
        
        return {
            "success": True,
            "message": "New OTP has been sent to your email address"
        }
    
    @staticmethod
    def reset_password(db: Session, email: str, reset_token: str, new_password: str) -> Dict[str, Any]:
        """Reset password using valid reset token"""
        # Check if reset token exists and is valid
        if reset_token not in password_reset_tokens:
            return {
                "success": False,
                "message": "Invalid or expired reset token"
            }
        
        token_data = password_reset_tokens[reset_token]
        
        # Check if token is expired
        if datetime.utcnow() > token_data['expires_at']:
            del password_reset_tokens[reset_token]
            return {
                "success": False,
                "message": "Reset token has expired. Please request a new OTP."
            }
        
        # Verify email matches
        if token_data['email'] != email:
            return {
                "success": False,
                "message": "Email mismatch"
            }
        
        # Get user
        user = db.query(User).filter(
            User.email == email,
            User.role == 'admin'
        ).first()
        
        if not user:
            return {
                "success": False,
                "message": "User not found"
            }
        
        # Validate password strength
        if len(new_password) < 8:
            return {
                "success": False,
                "message": "Password must be at least 8 characters long"
            }
        
        # Hash the new password
        user.password_hash = AuthService.get_password_hash(new_password)
        
        # Save to database
        db.commit()
        db.refresh(user)
        
        # Clean up used token
        del password_reset_tokens[reset_token]
        
        # Optional: Clean up any existing OTP for this email
        if email in otp_storage:
            del otp_storage[email]
        
        return {
            "success": True,
            "message": "Password reset successful. You can now login with your new password."
        }
    
    @staticmethod
    def cleanup_expired_otps():
        """Remove expired OTPs from storage"""
        current_time = datetime.utcnow()
        expired_emails = [
            email for email, data in otp_storage.items()
            if data['expires_at'] < current_time
        ]
        for email in expired_emails:
            del otp_storage[email]
        
        expired_tokens = [
            token for token, data in password_reset_tokens.items()
            if data['expires_at'] < current_time
        ]
        for token in expired_tokens:
            del password_reset_tokens[token]


# ==================== BRANCH SERVICE ====================
class BranchService:
    @staticmethod
    def create_branch(db: Session, branch_data) -> Branch:
        db_branch = Branch(**branch_data.dict())
        db.add(db_branch)
        db.commit()
        db.refresh(db_branch)
        return db_branch
    
    @staticmethod
    def get_branches(db: Session) -> List[Branch]:
        return db.query(Branch).all()
    
    @staticmethod
    def get_branch(db: Session, branch_id: int) -> Optional[Branch]:
        return db.query(Branch).filter(Branch.id == branch_id).first()
    
    @staticmethod
    def update_branch(db: Session, branch_id: int, branch_data) -> Optional[Branch]:
        branch = BranchService.get_branch(db, branch_id)
        if not branch:
            return None
        for key, value in branch_data.dict(exclude_unset=True).items():
            setattr(branch, key, value)
        db.commit()
        db.refresh(branch)
        return branch


# ==================== PRODUCT SERVICE ====================
class ProductService:
    @staticmethod
    def create_product(db: Session, product_data) -> Product:
        existing = db.query(Product).filter(Product.sku == product_data.sku).first()
        if existing:
            raise ValueError("SKU already exists")
        db_product = Product(**product_data.dict())
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        return db_product
    
    @staticmethod
    def get_products(db: Session, active: Optional[bool] = True, branch_id: Optional[int] = None) -> List[Product]:
        query = db.query(Product)
        if active is not None:
            query = query.filter(Product.active == active)
        products = query.all()
        if branch_id:
            for product in products:
                stock = db.query(Stock).filter(
                    Stock.branch_id == branch_id,
                    Stock.product_id == product.id
                ).first()
                product.stock_quantity = stock.quantity if stock else 0
                product.reorder_level = stock.reorder_level if stock else 0
        return products
    
    @staticmethod
    def get_product(db: Session, product_id: int) -> Optional[Product]:
        return db.query(Product).filter(Product.id == product_id).first()
    
    @staticmethod
    def update_product(db: Session, product_id: int, product_data) -> Optional[Product]:
        product = ProductService.get_product(db, product_id)
        if not product:
            return None
        for key, value in product_data.dict(exclude_unset=True).items():
            setattr(product, key, value)
        db.commit()
        db.refresh(product)
        return product
    
    @staticmethod
    def delete_product(db: Session, product_id: int) -> bool:
        product = ProductService.get_product(db, product_id)
        if not product:
            return False
        db.delete(product)
        db.commit()
        return True


# ==================== STOCK SERVICE ====================
class StockService:
    @staticmethod
    def get_stock(db: Session, branch_id: int, product_id: int) -> Optional[Stock]:
        return db.query(Stock).filter(
            and_(Stock.branch_id == branch_id, Stock.product_id == product_id)
        ).first()
    
    @staticmethod
    def get_branch_stock(db: Session, branch_id: int, low_stock: bool = False) -> List[Dict]:
        query = db.query(Stock).filter(Stock.branch_id == branch_id)
        if low_stock:
            query = query.filter(Stock.quantity <= Stock.reorder_level)
        stocks = query.all()
        result = []
        for stock in stocks:
            product = db.query(Product).filter(Product.id == stock.product_id).first()
            result.append({
                "product": product,
                "quantity": float(stock.quantity),
                "reorder_level": float(stock.reorder_level),
                "status": "low" if stock.quantity <= stock.reorder_level else "normal"
            })
        return result
    
    @staticmethod
    def add_stock(db: Session, branch_id: int, product_id: int, quantity: float, 
                  user_id: int, notes: str = "") -> Stock:
        stock = StockService.get_stock(db, branch_id, product_id)
        if stock:
            stock.quantity += quantity
        else:
            stock = Stock(
                branch_id=branch_id,
                product_id=product_id,
                quantity=quantity,
                reorder_level=0
            )
            db.add(stock)
            db.flush()
        movement = StockMovement(
            branch_id=branch_id,
            product_id=product_id,
            user_id=user_id,
            change_qty=quantity,
            movement_type="purchase",
            notes=notes
        )
        db.add(movement)
        db.commit()
        db.refresh(stock)
        return stock
    
    @staticmethod
    def deduct_stock(db: Session, branch_id: int, product_id: int, quantity: float, 
                     user_id: int, reference_id: int, notes: str = "") -> Stock:
        stock = StockService.get_stock(db, branch_id, product_id)
        if not stock or stock.quantity < quantity:
            raise ValueError("Insufficient stock")
        stock.quantity -= quantity
        movement = StockMovement(
            branch_id=branch_id,
            product_id=product_id,
            user_id=user_id,
            change_qty=-quantity,
            movement_type="sale",
            reference_id=reference_id,
            notes=notes
        )
        db.add(movement)
        if stock.quantity <= 0:
            product = db.query(Product).filter(Product.id == product_id).first()
            alert = Alert(
                branch_id=branch_id,
                product_id=product_id,
                message=f"Product {product.name if product else product_id} is out of stock at branch {branch_id}",
                resolved=False
            )
            db.add(alert)
        db.commit()
        db.refresh(stock)
        return stock
    
    @staticmethod
    def update_reorder_level(db: Session, branch_id: int, product_id: int, reorder_level: float) -> Stock:
        stock = StockService.get_stock(db, branch_id, product_id)
        if not stock:
            raise ValueError("Stock not found")
        stock.reorder_level = reorder_level
        db.commit()
        db.refresh(stock)
        return stock


# ==================== SALE SERVICE ====================
class SaleService:
    @staticmethod
    def create_sale(db: Session, sale_data: SaleCreate, user_id: int, branch_id: int) -> Sale:
        for item in sale_data.items:
            stock = StockService.get_stock(db, branch_id, item.product_id)
            if not stock or stock.quantity < item.quantity:
                product = db.query(Product).filter(Product.id == item.product_id).first()
                raise ValueError(f"Insufficient stock for product: {product.name if product else item.product_id}")
        
        total_amount = 0.0
        total_cost = 0.0
        for item in sale_data.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                total_amount += item.quantity * item.unit_price
                total_cost += item.quantity * float(product.cost)
        
        db_sale = Sale(
            branch_id=branch_id,
            user_id=user_id,
            customer_name=sale_data.customer_name,
            total_amount=total_amount,
            total_cost=total_cost
        )
        db.add(db_sale)
        db.flush()
        
        for item in sale_data.items:
            line_total = item.quantity * item.unit_price
            sale_item = SaleItem(
                sale_id=db_sale.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=line_total
            )
            db.add(sale_item)
            StockService.deduct_stock(
                db, branch_id, item.product_id, item.quantity,
                user_id, db_sale.id, f"Sale #{db_sale.id}"
            )
        
        db.commit()
        db.refresh(db_sale)
        return db_sale
    
    @staticmethod
    def get_sales(db: Session, branch_id: int = None, user_id: int = None,
                  start_date: datetime = None, end_date: datetime = None, 
                  limit: int = 100) -> List[Sale]:
        query = db.query(Sale)
        if branch_id:
            query = query.filter(Sale.branch_id == branch_id)
        if user_id:
            query = query.filter(Sale.user_id == user_id)
        if start_date:
            query = query.filter(Sale.created_at >= start_date)
        if end_date:
            query = query.filter(Sale.created_at <= end_date)
        return query.order_by(Sale.created_at.desc()).limit(limit).all()


# ==================== REPORT SERVICE ====================
class ReportService:
    @staticmethod
    def generate_sales_report(db: Session, report_type: str, branch_id: Optional[int] = None) -> Dict:
        now = datetime.now()
        if report_type == "weekly":
            start_date = now - timedelta(days=7)
        elif report_type == "monthly":
            start_date = now - timedelta(days=30)
        else:
            raise ValueError("Report type must be 'weekly' or 'monthly'")
        
        query = db.query(Sale).filter(Sale.created_at >= start_date)
        if branch_id:
            query = query.filter(Sale.branch_id == branch_id)
        
        sales = query.all()
        total_revenue = sum(float(sale.total_amount) for sale in sales)
        total_profit = sum(float(sale.total_amount - sale.total_cost) for sale in sales)
        
        product_sales = {}
        for sale in sales:
            for item in sale.items:
                if item.product_id not in product_sales:
                    product = db.query(Product).filter(Product.id == item.product_id).first()
                    product_sales[item.product_id] = {
                        "quantity": 0,
                        "revenue": 0,
                        "product_name": product.name if product else "Unknown",
                        "product_sku": product.sku if product else "N/A"
                    }
                product_sales[item.product_id]["quantity"] += float(item.quantity)
                product_sales[item.product_id]["revenue"] += float(item.line_total)
        
        best_sellers = sorted(product_sales.items(), key=lambda x: x[1]["quantity"], reverse=True)[:10]
        slow_movers = sorted(product_sales.items(), key=lambda x: x[1]["quantity"])[:10]
        
        return {
            "report_type": report_type,
            "period": {"start": start_date, "end": now},
            "summary": {
                "total_sales": len(sales),
                "total_revenue": total_revenue,
                "total_profit": total_profit,
                "average_sale_value": total_revenue / len(sales) if sales else 0
            },
            "best_selling_products": [
                {"product_id": pid, "product_name": data["product_name"], "product_sku": data["product_sku"], "quantity_sold": data["quantity"], "revenue": data["revenue"]}
                for pid, data in best_sellers
            ],
            "slow_moving_products": [
                {"product_id": pid, "product_name": data["product_name"], "product_sku": data["product_sku"], "quantity_sold": data["quantity"], "revenue": data["revenue"]}
                for pid, data in slow_movers
            ]
        }


# ==================== ALERT SERVICE ====================
class AlertService:
    @staticmethod
    def create_alert(db: Session, branch_id: int, product_id: int, message: str) -> Alert:
        alert = Alert(
            branch_id=branch_id,
            product_id=product_id,
            message=message,
            resolved=False
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert
    
    @staticmethod
    def get_alerts(db: Session, resolved: bool = False, branch_id: Optional[int] = None) -> List:
        """Get alerts with product and branch names"""
        query = db.query(Alert).filter(Alert.resolved == resolved)
        if branch_id:
            query = query.filter(Alert.branch_id == branch_id)
        
        alerts = query.order_by(Alert.created_at.desc()).all()
        
        result = []
        for alert in alerts:
            product = db.query(Product).filter(Product.id == alert.product_id).first()
            branch = db.query(Branch).filter(Branch.id == alert.branch_id).first()
            result.append({
                "id": alert.id,
                "branch_id": alert.branch_id,
                "branch_name": branch.name if branch else "Unknown Branch",
                "product_id": alert.product_id,
                "product_name": product.name if product else "Unknown Product",
                "product_sku": product.sku if product else "N/A",
                "message": alert.message,
                "created_at": alert.created_at,
                "resolved": alert.resolved,
                "resolved_at": alert.resolved_at
            })
        return result
    
    @staticmethod
    def resolve_alert(db: Session, alert_id: int):
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return None
        alert.resolved = True
        alert.resolved_at = datetime.now()
        db.commit()
        db.refresh(alert)
        return alert
    
    @staticmethod
    def check_low_stock_and_create_alerts(db: Session) -> int:
        """Check all stock items and create alerts for low stock and out of stock"""
        stocks = db.query(Stock).all()
        alerts_created = 0
        
        for stock in stocks:
            product = db.query(Product).filter(Product.id == stock.product_id).first()
            branch = db.query(Branch).filter(Branch.id == stock.branch_id).first()
            
            if not product or not branch:
                continue
            
            current_qty = float(stock.quantity) if stock.quantity else 0
            reorder_level = float(stock.reorder_level) if stock.reorder_level else 0
            
            # Check for out of stock
            if current_qty <= 0:
                existing_alert = db.query(Alert).filter(
                    and_(
                        Alert.branch_id == stock.branch_id,
                        Alert.product_id == stock.product_id,
                        Alert.resolved == False,
                        Alert.message.like("%out of stock%")
                    )
                ).first()
                
                if not existing_alert:
                    message = f"Out of stock: {product.name} (SKU: {product.sku}) is out of stock at {branch.name}."
                    alert = Alert(
                        branch_id=stock.branch_id,
                        product_id=stock.product_id,
                        message=message,
                        resolved=False
                    )
                    db.add(alert)
                    alerts_created += 1
            
            # Check for low stock
            elif current_qty <= reorder_level:
                existing_alert = db.query(Alert).filter(
                    and_(
                        Alert.branch_id == stock.branch_id,
                        Alert.product_id == stock.product_id,
                        Alert.resolved == False,
                        Alert.message.like("%low stock%")
                    )
                ).first()
                
                if not existing_alert:
                    message = f"Low stock alert: {product.name} (SKU: {product.sku}) has only {current_qty} units remaining at {branch.name}. Reorder level is {reorder_level}."
                    alert = Alert(
                        branch_id=stock.branch_id,
                        product_id=stock.product_id,
                        message=message,
                        resolved=False
                    )
                    db.add(alert)
                    alerts_created += 1
        
        if alerts_created > 0:
            db.commit()
        return alerts_created
    
    @staticmethod
    def auto_resolve_alerts(db: Session) -> int:
        """Auto-resolve alerts for products that are no longer low stock or out of stock"""
        unresolved_alerts = db.query(Alert).filter(Alert.resolved == False).all()
        resolved_count = 0
        
        for alert in unresolved_alerts:
            stock = db.query(Stock).filter(
                and_(
                    Stock.branch_id == alert.branch_id,
                    Stock.product_id == alert.product_id
                )
            ).first()
            
            if not stock:
                continue
            
            current_qty = float(stock.quantity) if stock.quantity else 0
            reorder_level = float(stock.reorder_level) if stock.reorder_level else 0
            
            if "out of stock" in alert.message.lower() and current_qty > 0:
                alert.resolved = True
                alert.resolved_at = datetime.now()
                resolved_count += 1
            elif "low stock" in alert.message.lower() and current_qty > reorder_level:
                alert.resolved = True
                alert.resolved_at = datetime.now()
                resolved_count += 1
        
        if resolved_count > 0:
            db.commit()
        return resolved_count
    
    @staticmethod
    def get_low_stock_summary(db: Session, branch_id: Optional[int] = None) -> Dict:
        """Get summary of all low stock items (including out of stock)"""
        query = db.query(Stock).filter(Stock.quantity <= Stock.reorder_level)
        if branch_id:
            query = query.filter(Stock.branch_id == branch_id)
        
        low_stock_items = query.all()
        result = []
        
        for stock in low_stock_items:
            product = db.query(Product).filter(Product.id == stock.product_id).first()
            branch = db.query(Branch).filter(Branch.id == stock.branch_id).first()
            
            if product and branch:
                current_stock = float(stock.quantity) if stock.quantity else 0
                reorder_level = float(stock.reorder_level) if stock.reorder_level else 0
                
                result.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "product_sku": product.sku,
                    "current_stock": current_stock,
                    "reorder_level": reorder_level,
                    "shortage": reorder_level - current_stock if current_stock < reorder_level else 0,
                    "branch_id": stock.branch_id,
                    "branch_name": branch.name,
                    "status": "out_of_stock" if current_stock <= 0 else "low_stock"
                })
        
        result.sort(key=lambda x: (x["status"] != "out_of_stock", x["current_stock"]))
        
        return {
            "total_low_stock_items": len(result),
            "items": result
        }


# ==================== SETTINGS SERVICE ====================
class SettingsService:
    
    @staticmethod
    def _get_value(setting) -> Any:
        if setting and setting.value:
            try:
                return json.loads(setting.value)
            except:
                return setting.value
        return None
    
    @staticmethod
    def _set_value(value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)
    
    @staticmethod
    def get_setting(db: Session, category: str, key: str) -> Any:
        setting = db.query(SystemSetting).filter(
            SystemSetting.category == category,
            SystemSetting.key == key
        ).first()
        return SettingsService._get_value(setting)
    
    @staticmethod
    def get_category_settings(db: Session, category: str) -> Dict[str, Any]:
        settings_list = db.query(SystemSetting).filter(SystemSetting.category == category).all()
        return {s.key: SettingsService._get_value(s) for s in settings_list}
    
    @staticmethod
    def set_setting(db: Session, category: str, key: str, value: Any, user_id: int = None) -> Any:
        setting = db.query(SystemSetting).filter(
            SystemSetting.category == category,
            SystemSetting.key == key
        ).first()
        
        old_value = SettingsService._get_value(setting) if setting else None
        
        if setting:
            setting.value = SettingsService._set_value(value)
        else:
            setting = SystemSetting(
                category=category,
                key=key,
                value=SettingsService._set_value(value)
            )
            db.add(setting)
        
        db.commit()
        db.refresh(setting)
        
        if user_id:
            log = SystemLog(
                log_type="settings",
                message=f"Setting changed: {category}.{key}",
                details=f"Old: {old_value}, New: {value}",
                user_id=user_id
            )
            db.add(log)
            db.commit()
        
        return SettingsService._get_value(setting)
    
    @staticmethod
    def set_multiple_settings(db: Session, category: str, settings_dict: Dict[str, Any], user_id: int = None):
        for key, value in settings_dict.items():
            SettingsService.set_setting(db, category, key, value, user_id)
    
    @staticmethod
    def get_all_settings(db: Session) -> Dict[str, Any]:
        settings_list = db.query(SystemSetting).all()
        result = {}
        for setting in settings_list:
            if setting.category not in result:
                result[setting.category] = {}
            result[setting.category][setting.key] = SettingsService._get_value(setting)
        return result
    
    @staticmethod
    def initialize_default_settings(db: Session):
        defaults = {
            "general": {
                "system_name": "Inventory System",
                "timezone": "Africa/Addis_Ababa",
                "date_format": "YYYY-MM-DD",
                "currency": "ETB",
                "language": "en",
                "items_per_page": 20
            },
            "notification": {
                "low_stock_email": True,
                "daily_report_email": True,
                "sms_alerts": False,
                "loan_overdue_alerts": True,
                "email_recipients": ["admin@example.com"],
                "sms_recipients": []
            },
            "backup": {
                "auto_backup": True,
                "frequency": "daily",
                "backup_time": "23:00",
                "location": "local",
                "retention_days": 30
            }
        }
        
        for category, category_settings in defaults.items():
            for key, value in category_settings.items():
                existing = db.query(SystemSetting).filter(
                    SystemSetting.category == category,
                    SystemSetting.key == key
                ).first()
                if not existing:
                    db.add(SystemSetting(
                        category=category,
                        key=key,
                        value=SettingsService._set_value(value)
                    ))
        db.commit()
    
    @staticmethod
    def get_system_info(db: Session) -> Dict:
        total_users = db.query(User).count()
        total_products = db.query(Product).count()
        total_branches = db.query(Branch).count()
        last_week = datetime.now() - timedelta(days=7)
        recent_sales = db.query(Sale).filter(Sale.created_at >= last_week).count()
        last_backup = db.query(BackupRecord).order_by(BackupRecord.created_at.desc()).first()
        active_loans = db.query(Loan).filter(Loan.status.in_(['active', 'partially_paid'])).count()
        cache_size = SettingsService.get_setting(db, "system", "cache_size") or 24.5
        
        return {
            "version": "2.0.0",
            "build_date": "2024-03-15",
            "database": "PostgreSQL/SQLite",
            "server_status": "online",
            "total_users": total_users,
            "total_products": total_products,
            "total_branches": total_branches,
            "recent_sales": recent_sales,
            "uptime_days": 45,
            "active_loans": active_loans,
            "last_backup": last_backup.created_at.isoformat() if last_backup else None,
            "cache_size_mb": float(cache_size),
            "last_cache_clear": SettingsService.get_setting(db, "system", "last_cache_clear")
        }
    
    @staticmethod
    def clear_cache() -> Dict:
        return {"cleared": True, "size_freed_mb": 24.5}
    
    @staticmethod
    def create_backup(db: Session, user_id: int = None) -> Dict[str, Any]:
        try:
            backup_dir = "backups"
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_{timestamp}.sql"
            backup_path = os.path.join(backup_dir, backup_filename)
            with open(backup_path, 'w') as f:
                f.write(f"-- Backup created at {datetime.now()}\n")
                f.write("-- Database backup content\n")
            file_size = os.path.getsize(backup_path) / (1024 * 1024)
            backup = BackupRecord(name=backup_filename, file_path=backup_path, size_mb=file_size, created_by=user_id)
            db.add(backup)
            db.commit()
            if user_id:
                log = SystemLog(log_type="backup", message=f"Backup created: {backup_filename}", details=f"Size: {file_size:.2f} MB", user_id=user_id)
                db.add(log)
                db.commit()
            return {"id": backup.id, "name": backup.name, "size_mb": file_size, "created_at": backup.created_at.isoformat()}
        except Exception as e:
            raise Exception(f"Failed to create backup: {str(e)}")
    
    @staticmethod
    def get_backups(db: Session, limit: int = 10) -> List[Dict]:
        backups = db.query(BackupRecord).order_by(BackupRecord.created_at.desc()).limit(limit).all()
        return [{"id": b.id, "name": b.name, "size_mb": float(b.size_mb), "created_at": b.created_at.isoformat(), "created_by": b.creator.name if b.creator else "System"} for b in backups]
    
    @staticmethod
    def delete_backup(db: Session, backup_id: int, user_id: int = None) -> bool:
        backup = db.query(BackupRecord).filter(BackupRecord.id == backup_id).first()
        if backup:
            if os.path.exists(backup.file_path):
                os.remove(backup.file_path)
            db.delete(backup)
            db.commit()
            if user_id:
                log = SystemLog(log_type="backup", message=f"Backup deleted: {backup.name}", user_id=user_id)
                db.add(log)
                db.commit()
            return True
        return False
    
    @staticmethod
    def export_all_data(db: Session) -> Dict:
        products = db.query(Product).all()
        branches = db.query(Branch).all()
        users = db.query(User).all()
        return {
            "export_date": datetime.now().isoformat(),
            "export_version": "2.0.0",
            "products": [{"id": p.id, "sku": p.sku, "name": p.name, "description": p.description, "color": p.color, "size": p.size, "price": float(p.price), "cost": float(p.cost), "active": p.active} for p in products],
            "branches": [{"id": b.id, "name": b.name, "address": b.address, "phone": b.phone} for b in branches],
            "users": [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "branch_id": u.branch_id, "active": u.active} for u in users]
        }
    
    @staticmethod
    def reset_system_data(db: Session, user_id: int = None) -> Dict:
        try:
            db.query(Loan).delete()
            db.query(SaleItem).delete()
            db.query(Sale).delete()
            db.query(PurchaseItem).delete()
            db.query(Purchase).delete()
            db.query(StockMovement).delete()
            db.query(Stock).delete()
            db.query(Alert).delete()
            db.commit()
            if user_id:
                log = SystemLog(log_type="warning", message="System data reset", details="All transactional data has been cleared", user_id=user_id)
                db.add(log)
                db.commit()
            return {"message": "System data reset successfully"}
        except Exception as e:
            db.rollback()
            raise Exception(f"Failed to reset data: {str(e)}")