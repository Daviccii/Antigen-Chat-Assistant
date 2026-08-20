"""Authentication service for user management and authentication logic."""
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from .models import User, UserRole
from .auth import get_password_hash, verify_password, create_access_token


class AuthService:
    """Service for handling authentication operations."""
    
    @staticmethod
    def create_user(
        db: Session,
        username: str,
        password: str,
        display_name: str,
        email: Optional[str] = None,
        role: UserRole = UserRole.USER
    ) -> User:
        """Create a new user with hashed password."""
        # Check if username already exists
        if db.query(User).filter(User.username == username).first():
            raise ValueError("Username already exists")
        
        # Check if email already exists (if provided)
        if email and db.query(User).filter(User.email == email).first():
            raise ValueError("Email already exists")
        
        # Create user with hashed password
        hashed_password = get_password_hash(password)
        user = User(
            username=username,
            email=email,
            display_name=display_name,
            hashed_password=hashed_password,
            role=role,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """Authenticate a user by username and password."""
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        return user
    
    @staticmethod
    def login_user(db: Session, username: str, password: str) -> Optional[tuple[User, str]]:
        """Login a user and return user with access token."""
        user = AuthService.authenticate_user(db, username, password)
        if not user:
            return None
        
        # Create access token
        access_token = create_access_token(data={"sub": user.username})
        return user, access_token
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get a user by ID."""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        """Get a user by username."""
        return db.query(User).filter(User.username == username).first()
    
    @staticmethod
    def update_user_password(db: Session, user: User, new_password: str) -> User:
        """Update a user's password."""
        user.hashed_password = get_password_hash(new_password)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def initialize_first_owner(db: Session, username: str, password: str, display_name: str) -> User:
        """Initialize the first owner if no users exist."""
        # Check if any users exist
        if db.query(User).count() > 0:
            raise ValueError("Users already exist. Cannot initialize first owner.")
        
        return AuthService.create_user(
            db=db,
            username=username,
            password=password,
            display_name=display_name,
            role=UserRole.OWNER
        )