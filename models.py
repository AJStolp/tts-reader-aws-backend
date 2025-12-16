import uuid
import secrets
from datetime import datetime, timedelta
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from passlib.context import CryptContext
import enum

# Create Base here to avoid circular imports
Base = declarative_base()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Tier enumeration
class UserTier(enum.Enum):
    FREE = "FREE"
    PREMIUM = "PREMIUM"
    PRO = "PRO"

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
    stripe_price_id = Column(String(128), nullable=True)

    # Tier and usage tracking
    tier = Column(Enum(UserTier), default=UserTier.FREE, nullable=False)
    monthly_usage = Column(Integer, default=0, nullable=False)
    usage_reset_date = Column(DateTime, default=lambda: datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0), nullable=False)

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

        # Truncate password to 72 bytes for bcrypt compatibility
        password_bytes = password.encode('utf-8')[:72]
        password_truncated = password_bytes.decode('utf-8', errors='ignore')

        self.password_hash = pwd_context.hash(password_truncated)
    
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

        # Truncate password to 72 bytes for bcrypt compatibility
        password_bytes = password.encode('utf-8')[:72]
        password_truncated = password_bytes.decode('utf-8', errors='ignore')

        return pwd_context.verify(password_truncated, self.password_hash)
    
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

    def get_monthly_cap(self) -> int:
        """
        Get monthly character cap based on user tier.

        Returns:
            int: Monthly character limit (0 for unlimited)
        """
        tier_caps = {
            UserTier.FREE: 0,  # Unlimited but only web speech API
            UserTier.PREMIUM: 2_000_000,  # 2M characters
            UserTier.PRO: 10_000_000  # 10M characters
        }
        return tier_caps.get(self.tier, 0)

    def check_and_reset_monthly_usage(self) -> None:
        """
        Check if monthly usage should be reset (on 1st of month).
        Resets usage counter if reset date has passed.
        """
        now = datetime.utcnow()
        if now >= self.usage_reset_date:
            # Calculate next reset date (1st of next month)
            if now.month == 12:
                next_reset = datetime(now.year + 1, 1, 1, 0, 0, 0)
            else:
                next_reset = datetime(now.year, now.month + 1, 1, 0, 0, 0)

            self.monthly_usage = 0
            self.usage_reset_date = next_reset
            self.updated_at = now

    def can_use_characters(self, char_count: int) -> tuple[bool, str]:
        """
        Check if user can use the requested number of characters.

        Args:
            char_count (int): Number of characters to use

        Returns:
            tuple[bool, str]: (can_use, reason) - True if allowed, False with reason if not
        """
        # Reset usage if needed
        self.check_and_reset_monthly_usage()

        # Free tier can't use Polly (unlimited web speech API only)
        if self.tier == UserTier.FREE:
            return False, "Free tier users cannot use AWS Polly. Upgrade to Premium or Pro."

        monthly_cap = self.get_monthly_cap()

        # If cap is 0, it's unlimited (shouldn't happen for paid tiers but safe check)
        if monthly_cap == 0:
            return True, ""

        # Check if adding this would exceed the cap
        if self.monthly_usage + char_count > monthly_cap:
            return False, f"Monthly limit reached. Used: {self.monthly_usage:,}/{monthly_cap:,} characters."

        return True, ""

    def track_character_usage(self, char_count: int) -> None:
        """
        Track character usage for the current month.

        Args:
            char_count (int): Number of characters used
        """
        if char_count < 0:
            raise ValueError("Character count cannot be negative")

        self.check_and_reset_monthly_usage()
        self.monthly_usage += char_count
        self.updated_at = datetime.utcnow()

    def get_usage_percentage(self) -> float:
        """
        Get current usage as percentage of monthly cap.

        Returns:
            float: Usage percentage (0-100), or 0 for unlimited
        """
        monthly_cap = self.get_monthly_cap()
        if monthly_cap == 0:
            return 0.0

        return (self.monthly_usage / monthly_cap) * 100

    def is_near_limit(self, threshold: float = 80.0) -> bool:
        """
        Check if user is approaching their monthly limit.

        Args:
            threshold (float): Percentage threshold (default 80%)

        Returns:
            bool: True if usage is above threshold
        """
        return self.get_usage_percentage() >= threshold

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """
        Convert user object to dictionary.
        
        Args:
            include_sensitive (bool): Whether to include sensitive information
            
        Returns:
            dict: User data as dictionary
        """
        # Ensure usage is current
        self.check_and_reset_monthly_usage()

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
            "tier": self.tier.value.lower() if self.tier else "free",
            "monthly_usage": self.monthly_usage,
            "monthly_cap": self.get_monthly_cap(),
            "usage_percentage": round(self.get_usage_percentage(), 2),
            "usage_reset_date": self.usage_reset_date.isoformat() if self.usage_reset_date else None,
            "is_near_limit": self.is_near_limit(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_sensitive:
            data.update({
                "stripe_subscription_id": self.stripe_subscription_id,
                "stripe_price_id": self.stripe_price_id,
            })

        return data
    
    def __repr__(self) -> str:
        """String representation of User object"""
        return f"<User(username='{self.username}', email='{self.email}', active={self.is_active})>"