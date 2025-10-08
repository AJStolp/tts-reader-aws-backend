import uuid
import secrets
from datetime import datetime, timedelta
from sqlalchemy import Column, String, Integer, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from passlib.context import CryptContext

# Create Base here to avoid circular imports
Base = declarative_base()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    """Enhanced User model with Supabase UUID support and modern security"""
    __tablename__ = "users"
    
    # Primary key using PostgreSQL UUID
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # User identification
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False, index=True)
    
    # Personal information
    first_name = Column(String(128), nullable=True)
    last_name = Column(String(128), nullable=True)
    
    # Authentication
    password_hash = Column(String(255), nullable=False)
    
    # Usage tracking
    remaining_chars = Column(Integer, default=100000, nullable=False)
    
    # User preferences for TTS
    engine = Column(String(20), default="standard", nullable=False)
    voice_id = Column(String(50), default="Joanna", nullable=False)
    
    # Subscription management
    stripe_subscription_id = Column(String(128), nullable=True)
    
    # Account status and metadata
    is_active = Column(Boolean, default=True, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verification_token = Column(String(255), nullable=True)
    email_verification_token_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def set_password(self, password: str) -> None:
        """
        Hash and set the user's password using bcrypt.
        
        Args:
            password (str): Plain text password to hash
        """
        if not password:
            raise ValueError("Password cannot be empty")
        
        self.password_hash = pwd_context.hash(password)
    
    def check_password(self, password: str) -> bool:
        """
        Check if the provided password matches the stored hash.
        
        Args:
            password (str): Plain text password to verify
            
        Returns:
            bool: True if password matches, False otherwise
        """
        if not password or not self.password_hash:
            return False
        
        return pwd_context.verify(password, self.password_hash)
    
    def update_last_login(self) -> None:
        """Update the last login timestamp"""
        self.last_login = datetime.utcnow()
    
    def deduct_characters(self, char_count: int) -> bool:
        """
        Deduct characters from user's remaining balance.
        
        Args:
            char_count (int): Number of characters to deduct
            
        Returns:
            bool: True if deduction successful, False if insufficient balance
        """
        if char_count < 0:
            raise ValueError("Character count cannot be negative")
        
        if self.remaining_chars >= char_count:
            self.remaining_chars -= char_count
            return True
        return False
    
    def add_characters(self, char_count: int) -> None:
        """
        Add characters to user's balance (for upgrades/refunds).
        
        Args:
            char_count (int): Number of characters to add
        """
        if char_count < 0:
            raise ValueError("Character count cannot be negative")
        
        self.remaining_chars += char_count
    
    def get_usage_stats(self) -> dict:
        """
        Get user usage statistics.
        
        Returns:
            dict: Usage statistics including used and remaining characters
        """
        total_chars = 100000  # Default allocation
        used_chars = total_chars - self.remaining_chars
        
        return {
            "user_id": str(self.user_id),
            "username": self.username,
            "total_chars": total_chars,
            "used_chars": max(0, used_chars),
            "remaining_chars": self.remaining_chars,
            "usage_percentage": (used_chars / total_chars) * 100 if total_chars > 0 else 0,
            "engine": self.engine,
            "voice_id": self.voice_id,
            "is_active": self.is_active,
            "last_login": self.last_login,
            "created_at": self.created_at
        }
    
    def update_preferences(self, engine: str = None, voice_id: str = None) -> None:
        """
        Update user TTS preferences.
        
        Args:
            engine (str, optional): TTS engine preference
            voice_id (str, optional): Voice ID preference
        """
        if engine is not None:
            if engine not in ["standard", "neural"]:
                raise ValueError("Engine must be 'standard' or 'neural'")
            self.engine = engine
        
        if voice_id is not None:
            if not voice_id.strip():
                raise ValueError("Voice ID cannot be empty")
            self.voice_id = voice_id
        
        self.updated_at = datetime.utcnow()

    def generate_email_verification_token(self) -> str:
        """
        Generate a secure email verification token.

        Returns:
            str: The generated verification token
        """
        token = secrets.token_urlsafe(32)
        self.email_verification_token = token
        self.email_verification_token_expires = datetime.utcnow() + timedelta(hours=24)
        return token

    def verify_email_token(self, token: str) -> bool:
        """
        Verify the email verification token.

        Args:
            token (str): The token to verify

        Returns:
            bool: True if token is valid and not expired, False otherwise
        """
        if not self.email_verification_token or not self.email_verification_token_expires:
            return False

        if datetime.utcnow() > self.email_verification_token_expires:
            return False

        if self.email_verification_token != token:
            return False

        return True

    def mark_email_verified(self) -> None:
        """Mark the user's email as verified and clear verification token."""
        self.email_verified = True
        self.email_verification_token = None
        self.email_verification_token_expires = None
        self.updated_at = datetime.utcnow()

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """
        Convert user object to dictionary.
        
        Args:
            include_sensitive (bool): Whether to include sensitive information
            
        Returns:
            dict: User data as dictionary
        """
        data = {
            "user_id": str(self.user_id),
            "username": self.username,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "remaining_chars": self.remaining_chars,
            "engine": self.engine,
            "voice_id": self.voice_id,
            "is_active": self.is_active,
            "email_verified": self.email_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_sensitive:
            data.update({
                "stripe_subscription_id": self.stripe_subscription_id,
            })
        
        return data
    
    def __repr__(self) -> str:
        """String representation of User object"""
        return f"<User(username='{self.username}', email='{self.email}', active={self.is_active})>"