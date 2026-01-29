"""
Authentication and security utilities for TTS Reader API
"""
import logging
import smtplib
import asyncio
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import config
from .dittofeed import dittofeed_service, fire_and_forget
from database import get_db
from models import User

logger = logging.getLogger(__name__)

# Security configuration with automatic truncation for bcrypt
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__truncate_error=False  # Auto-truncate passwords longer than 72 bytes
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/token")

class AuthManager:
    """Centralized authentication management"""
    
    def __init__(self):
        self.secret_key = config.JWT_SECRET_KEY
        self.algorithm = config.ALGORITHM
        self.access_token_expire_minutes = config.ACCESS_TOKEN_EXPIRE_MINUTES
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        # Truncate password to 72 bytes for bcrypt compatibility
        password_bytes = plain_password.encode('utf-8')[:72]
        password_truncated = password_bytes.decode('utf-8', errors='ignore')
        return pwd_context.verify(password_truncated, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Generate password hash"""
        # Truncate password to 72 bytes for bcrypt compatibility
        password_bytes = password.encode('utf-8')[:72]
        password_truncated = password_bytes.decode('utf-8', errors='ignore')
        return pwd_context.hash(password_truncated)
    
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
    
    def authenticate_user(self, db: Session, username: str, password: str, require_email_verification: bool = True) -> Optional[User]:
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

        if require_email_verification and not user.email_verified:
            logger.warning(f"Login failed - email not verified for user: {username}")
            raise HTTPException(
                status_code=403,
                detail="Email verification required. Please check your email and verify your account."
            )

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

        # TEMPORARILY DISABLED - Email verification check for API access
        # if not user.email_verified:
        #     raise HTTPException(
        #         status_code=403,
        #         detail="Email verification required. Please verify your email to access this resource."
        #     )

        return user

    def send_verification_email(self, user: User, verification_token: str) -> bool:
        """Send email verification email to user"""
        try:
            print(f"DEBUG: Starting email send process...")
            print(f"DEBUG: SMTP_HOST={config.SMTP_HOST}")
            print(f"DEBUG: SMTP_PORT={config.SMTP_PORT}")
            print(f"DEBUG: SMTP_USERNAME={config.SMTP_USERNAME}")
            print(f"DEBUG: SMTP_USE_TLS={config.SMTP_USE_TLS}")

            if not all([config.SMTP_HOST, config.SMTP_USERNAME, config.SMTP_PASSWORD]):
                logger.warning("SMTP configuration incomplete, cannot send verification email")
                return False

            # Create verification URL
            verification_url = f"{config.FRONTEND_URL}/email-verification?token={verification_token}"
            print(f"{verification_url=}")

            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = "Verify your TTS Reader account"
            msg['From'] = "tts@logantaylorandkitties.com"
            msg['To'] = user.email
            print(f"DEBUG: Message created for {user.email}")

            # Create HTML content
            html_content = f"""
            <html>
                <body>
                    <h2>Welcome to TTS Reader!</h2>
                    <p>Hi {user.first_name or user.username},</p>
                    <p>Thank you for signing up for TTS Reader. To complete your registration, please verify your email address by clicking the link below:</p>
                    <p><a href="{verification_url}" style="background-color: #4CAF50; color: white; padding: 14px 20px; text-decoration: none; border-radius: 4px; display: inline-block;">Verify Email Address</a></p>
                    <p>If the button doesn't work, you can copy and paste this link into your browser:</p>
                    <p>{verification_url}</p>
                    <p>This verification link will expire in 24 hours.</p>
                    <p>If you didn't create an account with TTS Reader, you can safely ignore this email.</p>
                    <br>
                    <p>Best regards,<br>The TTS Reader Team</p>
                </body>
            </html>
            """

            # Create text content
            text_content = f"""
            Welcome to TTS Reader!

            Hi {user.first_name or user.username},

            Thank you for signing up for TTS Reader. To complete your registration, please verify your email address by visiting this link:

            {verification_url}

            This verification link will expire in 24 hours.

            If you didn't create an account with TTS Reader, you can safely ignore this email.

            Best regards,
            The TTS Reader Team
            """

            # Attach parts
            part1 = MIMEText(text_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            msg.attach(part1)
            msg.attach(part2)

            # Send email with timeout
            print(f"DEBUG: Attempting SMTP connection...")
            try:
                # Use SMTP_SSL for port 465, SMTP for port 587
                if config.SMTP_PORT == 465:
                    print(f"DEBUG: Using SMTP_SSL for port 465")
                    server_class = smtplib.SMTP_SSL
                    use_starttls = False
                else:
                    print(f"DEBUG: Using SMTP for port {config.SMTP_PORT}")
                    server_class = smtplib.SMTP
                    use_starttls = config.SMTP_USE_TLS

                with server_class(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
                    print(f"DEBUG: SMTP connection established")
                    server.set_debuglevel(1)  # Enable debug output

                    if use_starttls:
                        print(f"DEBUG: Starting TLS...")
                        server.starttls()
                        print(f"DEBUG: TLS established")

                    print(f"DEBUG: Attempting login...")
                    server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                    print(f"DEBUG: Login successful")

                    print(f"DEBUG: Sending message...")
                    server.send_message(msg)
                    print(f"DEBUG: Message sent successfully")

                logger.info(f"Verification email sent to {user.email}")
                return True

            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"SMTP Authentication failed: {str(e)}")
                print(f"DEBUG: SMTP Authentication Error - check username/password")
                return False
            except smtplib.SMTPConnectError as e:
                logger.error(f"SMTP Connection failed: {str(e)}")
                print(f"DEBUG: SMTP Connection Error - check host/port")
                return False
            except smtplib.SMTPException as e:
                logger.error(f"SMTP Error: {str(e)}")
                print(f"DEBUG: General SMTP Error: {str(e)}")
                return False
            except ConnectionRefusedError as e:
                logger.error(f"Connection refused: {str(e)}")
                print(f"DEBUG: Connection refused - server may be down")
                return False
            except Exception as e:
                logger.error(f"Unexpected error during email send: {str(e)}")
                print(f"DEBUG: Unexpected error: {type(e).__name__}: {str(e)}")
                return False

        except Exception as e:
            logger.error(f"Failed to send verification email to {user.email}: {str(e)}")
            print(f"DEBUG: Outer exception: {type(e).__name__}: {str(e)}")
            return False

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
    """Create a new user account with email verification"""
    try:
        # Create new user
        db_user = User(
            username=user_data["username"],
            email=user_data["email"],
            first_name=user_data.get("first_name"),
            last_name=user_data.get("last_name")
        )

        # Set password using the model method
        db_user.set_password(user_data["password"])

        # Generate email verification token
        print(f"email verification token about to be created")
        verification_token = db_user.generate_email_verification_token()

        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        # Track new user in Dittofeed
        fire_and_forget(dittofeed_service.identify(
            user_id=str(db_user.user_id),
            traits={
                "email": db_user.email,
                "username": db_user.username,
                "firstName": db_user.first_name,
                "lastName": db_user.last_name,
                "tier": "free",
                "emailVerified": False,
                "createdAt": db_user.created_at.isoformat() if db_user.created_at else None,
            }
        ))
        fire_and_forget(dittofeed_service.track(
            user_id=str(db_user.user_id),
            event="User Signed Up",
            properties={
                "username": db_user.username,
                "email": db_user.email,
                "firstName": db_user.first_name,
                "lastName": db_user.last_name,
            }
        ))

        # Send verification email
        print(f"email about to be sent")
        email_sent = auth_manager.send_verification_email(db_user, verification_token)
        if not email_sent:
            logger.warning(f"Failed to send verification email to {db_user.email}")

        logger.info(f"User {user_data['username']} registered successfully")
        return db_user

    except Exception as e:
        logger.error(f"Registration error for {user_data['username']}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred during registration"
        )

def verify_user_email(token: str, db: Session) -> dict:
    """Verify user email using verification token"""
    try:
        # Find user with this verification token
        user = db.query(User).filter(
            User.email_verification_token == token,
            User.email_verification_token_expires.isnot(None)
        ).first()

        if not user:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired verification token"
            )

        # Verify the token
        if not user.verify_email_token(token):
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired verification token"
            )

        # Mark email as verified
        user.mark_email_verified()
        db.commit()

        # Update Dittofeed profile and track verification
        fire_and_forget(dittofeed_service.identify(
            user_id=str(user.user_id),
            traits={
                "emailVerified": True,
                "email": user.email,
                "username": user.username,
            }
        ))
        fire_and_forget(dittofeed_service.track(
            user_id=str(user.user_id),
            event="Email Verified",
            properties={
                "username": user.username,
                "email": user.email,
            }
        ))

        logger.info(f"Email verified successfully for user: {user.username}")
        return {
            "message": "Email verified successfully",
            "user_id": str(user.user_id),
            "username": user.username
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred during email verification"
        )

def resend_verification_email(email: str, db: Session) -> dict:
    """Resend verification email to user"""
    try:
        # Find user by email
        user = db.query(User).filter(User.email == email).first()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        if user.email_verified:
            raise HTTPException(
                status_code=400,
                detail="Email is already verified"
            )

        # Generate new verification token
        verification_token = user.generate_email_verification_token()
        db.commit()

        # Send verification email
        email_sent = auth_manager.send_verification_email(user, verification_token)
        if not email_sent:
            logger.error(f"Failed to resend verification email to {user.email}")
            raise HTTPException(
                status_code=500,
                detail="Failed to send verification email"
            )

        logger.info(f"Verification email resent to {user.email}")
        return {
            "message": "Verification email sent successfully",
            "email": user.email
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend verification email error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred while resending verification email"
        )