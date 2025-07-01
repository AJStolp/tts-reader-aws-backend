"""
Authentication and security utilities for TTS Reader API
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import config
from database import get_db
from models import User

logger = logging.getLogger(__name__)

# Security configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/token")

class AuthManager:
    """Centralized authentication management"""
    
    def __init__(self):
        self.secret_key = config.JWT_SECRET_KEY
        self.algorithm = config.ALGORITHM
        self.access_token_expire_minutes = config.ACCESS_TOKEN_EXPIRE_MINUTES
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Generate password hash"""
        return pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, username: str) -> str:
        """Create JWT refresh token"""
        data = {"sub": username, "refresh": True}
        expires_delta = timedelta(days=7)
        return self.create_access_token(data, expires_delta)
    
    def decode_token(self, token: str) -> dict:
        """Decode and validate JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def authenticate_user(self, db: Session, username: str, password: str) -> Optional[User]:
        """Authenticate user credentials"""
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            logger.warning(f"Login failed - user not found: {username}")
            return None
        
        if not user.check_password(password):
            logger.warning(f"Login failed - incorrect password for user: {username}")
            return None
        
        if not user.is_active:
            logger.warning(f"Login failed - user account disabled: {username}")
            return None
        
        return user
    
    def get_current_user(self, token: str, db: Session) -> User:
        """Get current user from JWT token"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        payload = self.decode_token(token)
        username: str = payload.get("sub")
        
        if username is None:
            raise credentials_exception
        
        user = db.query(User).filter(
            User.username == username, 
            User.is_active == True
        ).first()
        
        if user is None:
            raise credentials_exception
        
        return user

# Global auth manager instance
auth_manager = AuthManager()

# Dependency functions for FastAPI
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """FastAPI dependency to get current authenticated user"""
    return auth_manager.get_current_user(token, db)

def validate_user_registration(username: str, email: str, db: Session) -> None:
    """Validate user registration data"""
    # Check if username exists
    existing_username = db.query(User).filter(User.username == username).first()
    if existing_username:
        raise HTTPException(
            status_code=400,
            detail=f"Username '{username}' already exists"
        )
    
    # Check if email exists
    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email:
        raise HTTPException(
            status_code=400,
            detail=f"Email '{email}' already registered"
        )

def create_user_account(user_data: dict, db: Session) -> User:
    """Create a new user account"""
    try:
        # Create new user
        db_user = User(
            username=user_data["username"],
            email=user_data["email"],
            first_name=user_data["first_name"],
            last_name=user_data["last_name"]
        )
        
        # Set password using the model method
        db_user.set_password(user_data["password"])
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        logger.info(f"User {user_data['username']} registered successfully")
        return db_user
        
    except Exception as e:
        logger.error(f"Registration error for {user_data['username']}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred during registration"
        )