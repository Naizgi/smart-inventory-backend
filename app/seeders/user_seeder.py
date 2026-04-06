# app/seeders/user_seeder.py
from sqlalchemy.orm import Session
from app.models import User, Branch
from app.services import AuthService
import logging
import bcrypt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_users(db: Session):
    """Seed users into the database"""
    
    # Check if users already exist
    existing_users = db.query(User).count()
    if existing_users > 0:
        logger.info(f"Users already exist ({existing_users} users). Skipping seeding.")
        return
    
    # Get branches (if any exist)
    branches = db.query(Branch).all()
    logger.info(f"Found {len(branches)} branches")
    
    # Create admin user with direct bcrypt hashing
    try:
        # Simple password hashing
        admin_password = "admin123"
        admin_password_hash = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        admin_user = User(
            name="Administrator",
            email="admin@example.com",
            password_hash=admin_password_hash,
            role="admin",
            branch_id=None,
            active=True
        )
        logger.info("Created admin user with bcrypt hash")
        
    except Exception as e:
        logger.error(f"Failed to create admin user: {e}")
        # Fallback to AuthService if available
        try:
            admin_user = User(
                name="Administrator",
                email="admin@example.com",
                password_hash=AuthService.get_password_hash("admin123"),
                role="admin",
                branch_id=None,
                active=True
            )
            logger.info("Created admin user with AuthService")
        except:
            logger.error("Could not create admin user with either method")
            return
    
    users = [admin_user]
    
    # Create salesmen if branches exist
    try:
        salesman_password = "salesman123"
        salesman_password_hash = bcrypt.hashpw(salesman_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        if branches:
            # Salesman 1
            salesman1 = User(
                name="John Salesman",
                email="salesman@example.com",
                password_hash=salesman_password_hash,
                role="salesman",
                branch_id=branches[0].id,
                active=True
            )
            users.append(salesman1)
            logger.info(f"Created salesman: John Salesman (Branch: {branches[0].name})")
            
            # Salesman 2 (if second branch exists)
            if len(branches) > 1:
                salesman2 = User(
                    name="Jane Sales",
                    email="jane@example.com",
                    password_hash=salesman_password_hash,
                    role="salesman",
                    branch_id=branches[1].id,
                    active=True
                )
                users.append(salesman2)
                logger.info(f"Created salesman: Jane Sales (Branch: {branches[1].name})")
            
            # Salesman 3
            salesman3 = User(
                name="Mike Johnson",
                email="mike@example.com",
                password_hash=salesman_password_hash,
                role="salesman",
                branch_id=branches[0].id,
                active=True
            )
            users.append(salesman3)
            logger.info(f"Created salesman: Mike Johnson (Branch: {branches[0].name})")
            
        else:
            logger.warning("No branches found. Creating users without branch assignments.")
            # Create salesmen without branches
            salesman1 = User(
                name="John Salesman",
                email="salesman@example.com",
                password_hash=salesman_password_hash,
                role="salesman",
                branch_id=None,
                active=True
            )
            users.append(salesman1)
            logger.info("Created salesman: John Salesman (No Branch)")
            
    except Exception as e:
        logger.error(f"Error creating salesmen: {e}")
    
    # Add all users to database
    try:
        db.add_all(users)
        db.commit()
        
        logger.info(f"✅ Successfully created {len(users)} users")
        logger.info("=" * 50)
        logger.info("Admin User:")
        logger.info("  Email: admin@example.com")
        logger.info("  Password: admin123")
        logger.info("  Role: Administrator")
        logger.info("-" * 30)
        logger.info("Salesman Users:")
        for user in users:
            if user.role == 'salesman':
                branch_name = user.branch.name if user.branch else "No Branch"
                logger.info(f"  {user.name}: {user.email} / salesman123 (Branch: {branch_name})")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"Failed to commit users to database: {e}")
        db.rollback()