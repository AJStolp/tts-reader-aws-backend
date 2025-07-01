import os
import time
import json
import logging
import io
import uuid
import stripe
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status, Request, WebSocket, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from pydub import AudioSegment
import asyncio
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from textract_processor import extract_content, ContentExtractorManager, ExtractionResult

# Import our Supabase-enabled database components
from database import get_db, health_check as db_health_check
from models import User

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Environment validation
REQUIRED_ENV_VARS = [
    "JWT_SECRET_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_REGION",
    "DATABASE_CONNECTION_STRING"
]

missing_vars = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# FastAPI app
app = FastAPI(
    title="TTS Reader API",
    description="Enhanced API for text extraction and synthesis with intelligent content processing",
    version="2.2.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enhanced CORS configuration
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000", 
    "https://localhost:3000"
]

# Get additional origins from environment if specified
env_origins = os.environ.get("ALLOWED_ORIGINS", "")
if env_origins:
    ALLOWED_ORIGINS.extend(env_origins.split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Security configuration
SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/token")

# AWS configuration with error handling
try:
    session = boto3.Session(
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_REGION", "us-east-1")
    )
    
    s3 = session.client("s3")
    polly = session.client("polly")
    
    # Test AWS credentials
    s3.list_buckets()
    polly.describe_voices(LanguageCode="en-US")
    
except (NoCredentialsError, ClientError) as e:
    logger.error(f"AWS configuration error: {str(e)}")
    raise ValueError("Invalid AWS credentials or configuration")

BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "tts-neural-reader-data")

# Stripe configuration
stripe.api_key = os.environ.get("STRIPE_API_KEY")

# Enhanced Pydantic models with better validation
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=6, max_length=128)
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=128)
    last_name: str = Field(..., min_length=1, max_length=128)

class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)

class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    remaining_chars: int
    engine: str
    voice_id: str
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None

class ExtractRequest(BaseModel):
    url: str = Field(..., pattern=r"^https?://.*")

class ExtractRequestEnhanced(BaseModel):
    url: str = Field(..., pattern=r"^https?://.*")
    prefer_textract: bool = Field(default=True, description="Whether to prefer Textract over DOM extraction")
    include_metadata: bool = Field(default=False, description="Whether to include extraction metadata")

class SynthesizeRequest(BaseModel):
    text_to_speech: str = Field(..., min_length=1, max_length=100000)
    voice_id: str = Field(default="Joanna", max_length=50)
    engine: str = Field(default="standard", pattern="^(standard|neural)$")

class ExtractResponse(BaseModel):
    text: str
    characters_used: int
    remaining_chars: int
    extraction_method: str

class ExtractResponseEnhanced(BaseModel):
    text: str
    characters_used: int
    remaining_chars: int
    extraction_method: str
    content_type: Optional[str] = None
    confidence: Optional[float] = None
    word_count: Optional[int] = None
    processing_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class SynthesizeResponse(BaseModel):
    audio_url: str
    speech_marks_url: str
    characters_used: int
    remaining_chars: int
    duration_seconds: float

class PreferencesUpdate(BaseModel):
    engine: Optional[str] = Field(None, pattern="^(standard|neural)$")
    voice_id: Optional[str] = Field(None, max_length=50)

class StripeCheckoutRequest(BaseModel):
    price_id: str = Field(default="price_1RcGYRQwS4m9kgMV6C1wAZcN")

class ExtractionProgress(BaseModel):
    status: str  # 'starting', 'processing', 'completed', 'failed'
    message: str
    progress: float  # 0.0 to 1.0
    method: Optional[str] = None
    timestamp: datetime

class ExtractionPreview(BaseModel):
    preview: str  # First 500 characters
    estimated_length: int
    confidence: float
    method: str
    full_available: bool

# Global storage for extraction progress (use Redis in production)
extraction_progress: Dict[str, List[ExtractionProgress]] = {}

# Utility functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if user is None:
        raise credentials_exception
    
    return user

# S3 bucket management
async def setup_bucket():
    """Setup S3 bucket with proper configuration"""
    try:
        # Check if bucket exists
        s3.head_bucket(Bucket=BUCKET_NAME)
        logger.info(f"Bucket {BUCKET_NAME} already exists")
    except ClientError as e:
        error_code = int(e.response["Error"]["Code"])
        if error_code == 404:
            # Create bucket
            try:
                if os.environ.get("AWS_REGION") == "us-east-1":
                    s3.create_bucket(Bucket=BUCKET_NAME)
                else:
                    s3.create_bucket(
                        Bucket=BUCKET_NAME,
                        CreateBucketConfiguration={
                            "LocationConstraint": os.environ.get("AWS_REGION")
                        }
                    )
                
                # Configure bucket security
                s3.put_public_access_block(
                    Bucket=BUCKET_NAME,
                    PublicAccessBlockConfiguration={
                        "BlockPublicAcls": True,
                        "IgnorePublicAcls": True,
                        "BlockPublicPolicy": True,
                        "RestrictPublicBuckets": True
                    }
                )
                
                # Enable versioning
                s3.put_bucket_versioning(
                    Bucket=BUCKET_NAME,
                    VersioningConfiguration={"Status": "Enabled"}
                )
                
                logger.info(f"Created and configured bucket {BUCKET_NAME}")
            except ClientError as create_error:
                logger.error(f"Failed to create bucket: {str(create_error)}")
                raise
        else:
            logger.error(f"Error accessing bucket: {str(e)}")
            raise

# Text processing utilities
MAX_POLLY_CHARS = 3000  # Conservative limit for Polly

def split_text_smart(text: str, max_length: int = MAX_POLLY_CHARS) -> list[str]:
    """Split text intelligently at sentence boundaries for TTS"""
    if len(text) <= max_length:
        return [text]
    
    sentences = text.replace('\n', ' ').split('. ')
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        test_chunk = current_chunk + sentence + ". "
        if len(test_chunk) > max_length and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = sentence + ". "
        else:
            current_chunk = test_chunk
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def cleanup_progress_data():
    """Clean up old progress data to prevent memory leaks"""
    if len(extraction_progress) > 100:
        # Sort by the latest timestamp and keep the most recent
        sorted_keys = sorted(
            extraction_progress.keys(),
            key=lambda k: extraction_progress[k][-1].timestamp if extraction_progress[k] else datetime.min,
            reverse=True
        )
        
        # Keep only the latest 50
        keys_to_keep = sorted_keys[:50]
        keys_to_remove = [k for k in extraction_progress.keys() if k not in keys_to_keep]
        
        for key in keys_to_remove:
            del extraction_progress[key]

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("Starting Enhanced TTS Reader API with intelligent content extraction...")
    
    # Setup S3 bucket
    await setup_bucket()
    
    logger.info("Application startup complete with enhanced extraction capabilities")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint"""
    db_health = await db_health_check()
    
    # Import and check extraction service health
    from textract_processor import health_check as extraction_health_check
    extraction_health = await extraction_health_check()
    
    overall_status = "healthy"
    if db_health["database"] != "healthy" or extraction_health["status"] != "healthy":
        overall_status = "degraded"
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.2.0",
        "database": db_health,
        "extraction_service": extraction_health,
        "aws_s3": "healthy",
        "aws_polly": "healthy"
    }

# Authentication endpoints
@app.post("/api/register", response_model=UserResponse)
async def register(request: Request, user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user with enhanced validation"""
    logger.info(f"Registration attempt for username: {user_data.username}")
    
    # Check if username exists
    existing_username = db.query(User).filter(User.username == user_data.username).first()
    if existing_username:
        raise HTTPException(
            status_code=400,
            detail=f"Username '{user_data.username}' already exists"
        )
    
    # Check if email exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=400,
            detail=f"Email '{user_data.email}' already registered"
        )
    
    try:
        # Create new user
        db_user = User(
            username=user_data.username,
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name
        )
        
        # Set password using the model method
        db_user.set_password(user_data.password)
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        logger.info(f"User {user_data.username} registered successfully")
        
        return UserResponse(
            user_id=str(db_user.user_id),
            username=db_user.username,
            email=db_user.email,
            first_name=db_user.first_name,
            last_name=db_user.last_name,
            remaining_chars=db_user.remaining_chars,
            engine=db_user.engine,
            voice_id=db_user.voice_id,
            created_at=db_user.created_at
        )
    except Exception as e:
        logger.error(f"Registration error for {user_data.username}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred during registration"
        )

@app.post("/api/login", response_model=Token)
async def login_json(request: Request, user_data: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return access token"""
    logger.info(f"Login attempt for username: {user_data.username}")
    
    # Find user by username
    db_user = db.query(User).filter(User.username == user_data.username).first()
    
    if not db_user:
        logger.warning(f"Login failed - user not found: {user_data.username}")
        raise HTTPException(
            status_code=401,
            detail=f"User '{user_data.username}' not found"
        )
    
    if not db_user.check_password(user_data.password):
        logger.warning(f"Login failed - incorrect password for user: {user_data.username}")
        raise HTTPException(
            status_code=401,
            detail="Incorrect password"
        )
    
    if not db_user.is_active:
        logger.warning(f"Login failed - user account disabled: {user_data.username}")
        raise HTTPException(
            status_code=401,
            detail="User account is disabled"
        )
    
    # Update last login
    db_user.update_last_login()
    db.commit()
    
    # Create tokens
    access_token = create_access_token(data={"sub": db_user.username})
    refresh_token = create_access_token(
        data={"sub": db_user.username, "refresh": True}, 
        expires_delta=timedelta(days=7)
    )
    
    logger.info(f"User {db_user.username} authenticated successfully")
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "refresh_token": refresh_token
    }

@app.get("/api/user", response_model=UserResponse)
async def get_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        user_id=str(current_user.user_id),
        username=current_user.username,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        remaining_chars=current_user.remaining_chars,
        engine=current_user.engine,
        voice_id=current_user.voice_id,
        created_at=current_user.created_at
    )

# Stripe integration endpoints
@app.post("/api/create-checkout-session")
async def create_checkout_session(
    request: StripeCheckoutRequest,
    current_user: User = Depends(get_current_user)
):
    """Create a Stripe checkout session for subscription"""
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": request.price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url="http://localhost:3000/success",
            cancel_url="http://localhost:3000/failed",
            client_reference_id=current_user.username,
        )
        
        logger.info(f"Created checkout session for user {current_user.username}")
        return {"url": checkout_session.url}
        
    except Exception as e:
        logger.error(f"Stripe checkout error for user {current_user.username}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create checkout session"
        )

@app.post("/api/stripe_webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.environ.get("STRIPE_WEBHOOK_SECRET")
        )
    except ValueError:
        logger.error("Invalid payload in Stripe webhook")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature in Stripe webhook")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        username = session["client_reference_id"]
        user = db.query(User).filter(User.username == username).first()
        
        if user:
            subscription_id = session["customer"]
            user.stripe_subscription_id = subscription_id
            db.commit()
            logger.info(f"Updated subscription ID for user {username}")

    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        # Find user by subscription ID and remove it
        user = db.query(User).filter(User.stripe_subscription_id == subscription["id"]).first()
        if user:
            user.stripe_subscription_id = None
            db.commit()
            logger.info(f"Removed subscription ID for user {user.username}")

    return {"status": "success"}

# Original content extraction endpoint (backwards compatibility)
@app.post("/api/extract", response_model=ExtractResponse)
async def extract_content_endpoint(
    request: ExtractRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Extract text content from URL (original endpoint for backwards compatibility)"""
    try:
        extracted_text, method = await extract_content(request.url)
        
        if not extracted_text:
            raise HTTPException(
                status_code=422,
                detail="Could not extract content from the provided URL"
            )
        
        text_length = len(extracted_text)
        
        if not current_user.deduct_characters(text_length):
            raise HTTPException(
                status_code=403,
                detail=f"Text length ({text_length}) exceeds remaining character limit ({current_user.remaining_chars})"
            )
        
        # Commit the character deduction
        db.commit()
        
        logger.info(f"Extracted {text_length} characters for user {current_user.username} using {method}")
        
        return ExtractResponse(
            text=extracted_text,
            characters_used=text_length,
            remaining_chars=current_user.remaining_chars,
            extraction_method=method
        )
        
    except Exception as e:
        logger.error(f"Extraction error for user {current_user.username}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred during content extraction"
        )

# Enhanced content extraction endpoints
@app.post("/api/extract/enhanced", response_model=ExtractResponseEnhanced)
async def extract_content_enhanced(
    request: ExtractRequestEnhanced,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Enhanced content extraction with better error handling and metadata for TTS"""
    extraction_id = str(uuid.uuid4())
    
    try:
        logger.info(f"Enhanced extraction request from user {current_user.username}: {request.url}")
        
        # Initialize progress tracking
        extraction_progress[extraction_id] = [
            ExtractionProgress(
                status="starting",
                message="Initializing TTS content extraction...",
                progress=0.0,
                timestamp=datetime.utcnow()
            )
        ]
        
        # Create extraction manager
        manager = ContentExtractorManager()
        
        # Update progress
        extraction_progress[extraction_id].append(
            ExtractionProgress(
                status="processing",
                message="Analyzing webpage and extracting TTS-optimized content...",
                progress=0.3,
                timestamp=datetime.utcnow()
            )
        )
        
        # Perform extraction
        start_time = time.time()
        extracted_text, method = await manager.extract_content(
            request.url, 
            prefer_textract=request.prefer_textract
        )
        processing_time = time.time() - start_time
        
        if not extracted_text:
            extraction_progress[extraction_id].append(
                ExtractionProgress(
                    status="failed",
                    message="Could not extract TTS content from the provided URL",
                    progress=1.0,
                    timestamp=datetime.utcnow()
                )
            )
            raise HTTPException(
                status_code=422,
                detail="Could not extract content from the provided URL"
            )
        
        text_length = len(extracted_text)
        
        # Update progress
        extraction_progress[extraction_id].append(
            ExtractionProgress(
                status="processing",
                message="Validating extracted TTS content...",
                progress=0.7,
                method=method,
                timestamp=datetime.utcnow()
            )
        )
        
        # Check character limits
        if not current_user.deduct_characters(text_length):
            extraction_progress[extraction_id].append(
                ExtractionProgress(
                    status="failed",
                    message=f"Text length ({text_length}) exceeds remaining character limit",
                    progress=1.0,
                    timestamp=datetime.utcnow()
                )
            )
            raise HTTPException(
                status_code=403,
                detail=f"Text length ({text_length}) exceeds remaining character limit ({current_user.remaining_chars})"
            )
        
        # Commit the character deduction
        db.commit()
        
        # Update progress
        extraction_progress[extraction_id].append(
            ExtractionProgress(
                status="completed",
                message="TTS content extraction completed successfully",
                progress=1.0,
                method=method,
                timestamp=datetime.utcnow()
            )
        )
        
        logger.info(f"Enhanced extraction completed for user {current_user.username}: "
                   f"{text_length} characters using {method} in {processing_time:.2f}s")
        
        # Prepare response
        response_data = {
            "text": extracted_text,
            "characters_used": text_length,
            "remaining_chars": current_user.remaining_chars,
            "extraction_method": method,
            "word_count": len(extracted_text.split()),
            "processing_time": processing_time
        }
        
        # Add metadata if requested
        if request.include_metadata:
            response_data["metadata"] = {
                "url": request.url,
                "extraction_id": extraction_id,
                "user_id": str(current_user.user_id),
                "timestamp": datetime.utcnow().isoformat(),
                "prefer_textract": request.prefer_textract,
                "optimized_for_tts": True
            }
        
        # Clean up progress data (keep last 5 extractions per user)
        cleanup_progress_data()
        
        return ExtractResponseEnhanced(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enhanced extraction error for user {current_user.username}: {str(e)}", exc_info=True)
        
        extraction_progress[extraction_id].append(
            ExtractionProgress(
                status="failed",
                message=f"An error occurred during TTS extraction: {str(e)}",
                progress=1.0,
                timestamp=datetime.utcnow()
            )
        )
        
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred during content extraction"
        )

@app.get("/api/extract/progress/{extraction_id}")
async def get_extraction_progress(
    extraction_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get real-time progress of content extraction"""
    if extraction_id not in extraction_progress:
        raise HTTPException(
            status_code=404,
            detail="Extraction progress not found"
        )
    
    progress_list = extraction_progress[extraction_id]
    latest_progress = progress_list[-1] if progress_list else None
    
    return {
        "extraction_id": extraction_id,
        "current_status": latest_progress.status if latest_progress else "unknown",
        "current_message": latest_progress.message if latest_progress else "No progress data",
        "progress": latest_progress.progress if latest_progress else 0.0,
        "method": latest_progress.method if latest_progress else None,
        "history": [p.dict() for p in progress_list[-5:]]  # Last 5 progress updates
    }

@app.post("/api/extract/preview")
async def extract_content_preview(
    request: ExtractRequest,
    current_user: User = Depends(get_current_user)
):
    """Get a preview of extracted TTS content without using character credits"""
    try:
        logger.info(f"Preview extraction request from user {current_user.username}: {request.url}")
        
        # Create extraction manager
        manager = ContentExtractorManager()
        
        # Perform extraction
        extracted_text, method = await manager.extract_content(request.url)
        
        if not extracted_text:
            raise HTTPException(
                status_code=422,
                detail="Could not extract content from the provided URL"
            )
        
        # Create preview (first 500 characters)
        preview = extracted_text[:500]
        if len(extracted_text) > 500:
            preview += "..."
        
        # Estimate confidence based on extraction method
        confidence_map = {
            "textract": 0.9,
            "dom_semantic": 0.8,
            "dom_heuristic": 0.7,
            "reader_mode": 0.6,
            "dom_fallback": 0.4
        }
        
        confidence = confidence_map.get(method, 0.5)
        
        return ExtractionPreview(
            preview=preview,
            estimated_length=len(extracted_text),
            confidence=confidence,
            method=method,
            full_available=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preview extraction error for user {current_user.username}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred during preview extraction"
        )

@app.get("/api/extract/methods")
async def get_extraction_methods(current_user: User = Depends(get_current_user)):
    """Get available extraction methods and their capabilities for TTS"""
    from textract_processor import health_check
    
    health_status = await health_check()
    
    methods = [
        {
            "id": "dom_semantic",
            "name": "DOM Semantic",
            "description": "Extract content using semantic HTML elements - optimized for TTS reading",
            "speed": "fast",
            "accuracy": "high",
            "tts_optimized": True,
            "available": health_status["playwright_available"]
        },
        {
            "id": "dom_heuristic", 
            "name": "DOM Heuristic",
            "description": "Extract content using content analysis algorithms - good for TTS",
            "speed": "fast",
            "accuracy": "medium-high",
            "tts_optimized": True,
            "available": health_status["playwright_available"]
        },
        {
            "id": "reader_mode",
            "name": "Reader Mode",
            "description": "Extract content using reader mode algorithm - clean TTS output",
            "speed": "fast",
            "accuracy": "medium",
            "tts_optimized": True,
            "available": health_status["playwright_available"]
        }
    ]
    
    # Add Textract if available
    if health_status["textract_available"]:
        methods.insert(0, {
            "id": "textract",
            "name": "AWS Textract",
            "description": "Extract content using AWS Textract OCR - highest accuracy for TTS",
            "speed": "medium",
            "accuracy": "very-high",
            "tts_optimized": True,
            "available": True
        })
    
    return {
        "methods": methods,
        "default_strategy": "intelligent_fallback_tts_optimized",
        "health_status": health_status,
        "service_type": "TTS Content Extraction"
    }

@app.get("/api/extract/analytics")
async def get_extraction_analytics(
    current_user: User = Depends(get_current_user),
    days: int = 7
):
    """Get TTS extraction analytics for the user"""
    # In a real implementation, you'd query your database for extraction history
    # For now, return mock data
    
    return {
        "period_days": days,
        "total_extractions": 42,
        "total_characters": 125000,
        "average_extraction_time": 3.2,
        "tts_optimized_extractions": 40,
        "methods_used": {
            "textract": 25,
            "dom_semantic": 12,
            "dom_heuristic": 3,
            "reader_mode": 2
        },
        "success_rate": 0.95,
        "average_confidence": 0.82,
        "most_common_sites": [
            {"domain": "wikipedia.org", "count": 8},
            {"domain": "medium.com", "count": 6},
            {"domain": "github.com", "count": 4}
        ],
        "content_types": {
            "articles": 22,
            "blog_posts": 12,
            "documentation": 6,
            "news": 2
        }
    }

# Text synthesis endpoint
@app.post("/api/synthesize", response_model=SynthesizeResponse)
async def synthesize_text(
    request: SynthesizeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Synthesize text to speech using Amazon Polly with enhanced TTS processing"""
    text_length = len(request.text_to_speech)
    
    if not current_user.deduct_characters(text_length):
        raise HTTPException(
            status_code=403,
            detail=f"Text length ({text_length}) exceeds remaining character limit ({current_user.remaining_chars})"
        )
    
    try:
        # Split text into chunks optimized for TTS
        chunks = split_text_smart(request.text_to_speech)
        audio_segments = []
        speech_marks_list = []
        cumulative_time = 0.0
        
        for chunk in chunks:
            # Synthesize audio
            audio_response = await asyncio.to_thread(
                polly.synthesize_speech,
                Text=chunk,
                OutputFormat="mp3",
                VoiceId=request.voice_id,
                Engine=request.engine
            )
            
            audio_stream = audio_response['AudioStream'].read()
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_stream), format="mp3")
            audio_segments.append(audio_segment)
            
            # Generate speech marks for TTS synchronization
            marks_response = await asyncio.to_thread(
                polly.synthesize_speech,
                Text=chunk,
                OutputFormat="json",
                VoiceId=request.voice_id,
                Engine=request.engine,
                SpeechMarkTypes=["word", "sentence"]
            )
            
            marks_text = marks_response['AudioStream'].read().decode('utf-8')
            chunk_marks = [json.loads(line) for line in marks_text.splitlines() if line.strip()]
            
            # Adjust timing for concatenated audio
            for mark in chunk_marks:
                mark['time'] += int(cumulative_time * 1000)
            
            speech_marks_list.extend(chunk_marks)
            cumulative_time += len(audio_segment) / 1000.0
        
        # Combine audio segments
        combined_audio = sum(audio_segments)
        audio_buffer = io.BytesIO()
        combined_audio.export(audio_buffer, format="mp3")
        audio_bytes = audio_buffer.getvalue()
        
        # Upload to S3
        timestamp = int(time.time())
        audio_key = f"users/{current_user.user_id}/audio/{timestamp}.mp3"
        marks_key = f"users/{current_user.user_id}/speech_marks/{timestamp}.json"
        
        # Upload audio file
        await asyncio.to_thread(
            s3.put_object,
            Bucket=BUCKET_NAME,
            Key=audio_key,
            Body=audio_bytes,
            ContentType="audio/mpeg"
        )
        
        # Upload speech marks
        marks_data = "\n".join([json.dumps(mark) for mark in speech_marks_list])
        await asyncio.to_thread(
            s3.put_object,
            Bucket=BUCKET_NAME,
            Key=marks_key,
            Body=marks_data,
            ContentType="application/json"
        )
        
        # Generate presigned URLs
        audio_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": audio_key},
            ExpiresIn=3600
        )
        
        speech_marks_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": marks_key},
            ExpiresIn=3600
        )
        
        # Commit the character deduction
        db.commit()
        
        duration = len(combined_audio) / 1000.0
        
        logger.info(f"Synthesized {text_length} characters for user {current_user.username}")
        
        return SynthesizeResponse(
            audio_url=audio_url,
            speech_marks_url=speech_marks_url,
            characters_used=text_length,
            remaining_chars=current_user.remaining_chars,
            duration_seconds=duration
        )
        
    except Exception as e:
        logger.error(f"Synthesis error for user {current_user.username}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred during text synthesis"
        )

# Get available voices
@app.get("/api/voices")
async def get_voices(current_user: User = Depends(get_current_user)):
    """Get available Polly voices grouped by engine for TTS"""
    try:
        response = await asyncio.to_thread(
            polly.describe_voices,
            LanguageCode="en-US"
        )
        
        # Group voices by supported engines
        standard_voices = []
        neural_voices = []
        
        for voice in response["Voices"]:
            voice_data = {
                "id": voice["Id"],
                "name": voice["Name"],
                "gender": voice["Gender"],
                "language": voice["LanguageName"],
                "tts_optimized": True
            }
            
            # Check which engines this voice supports
            supported_engines = voice["SupportedEngines"]
            
            if "standard" in supported_engines:
                standard_voices.append(voice_data)
            
            if "neural" in supported_engines:
                neural_voices.append(voice_data)
        
        return {
            "standard": standard_voices,
            "neural": neural_voices,
            "all": standard_voices + neural_voices,  # For convenience
            "recommendation": "Neural voices provide more natural TTS output"
        }
        
    except Exception as e:
        logger.error(f"Error fetching voices: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve available voices"
        )

# User preferences endpoints
@app.get("/api/preferences")
async def get_preferences(current_user: User = Depends(get_current_user)):
    """Get user TTS preferences"""
    return {
        "voice_id": current_user.voice_id,
        "engine": current_user.engine,
        "remaining_chars": current_user.remaining_chars,
        "user_id": str(current_user.user_id),
        "username": current_user.username,
        "tts_optimized": True
    }

@app.post("/api/preferences")
async def update_preferences(
    preferences: PreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user TTS preferences"""
    try:
        current_user.update_preferences(
            engine=preferences.engine,
            voice_id=preferences.voice_id
        )
        
        db.commit()
        logger.info(f"Updated TTS preferences for user {current_user.username}")
        
        return {
            "voice_id": current_user.voice_id,
            "engine": current_user.engine,
            "message": "TTS preferences updated successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating preferences for {current_user.username}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred while updating preferences"
        )

# Usage endpoint
@app.get("/api/usage")
async def get_usage(current_user: User = Depends(get_current_user)):
    """Get user TTS usage statistics"""
    usage_stats = current_user.get_usage_stats()
    return {
        "user_id": usage_stats["user_id"],
        "username": usage_stats["username"],
        "remaining_chars": usage_stats["remaining_chars"],
        "used_chars": usage_stats["used_chars"],
        "total_chars": usage_stats["total_chars"],
        "usage_percentage": usage_stats["usage_percentage"],
        "engine": usage_stats["engine"],
        "voice_id": usage_stats["voice_id"],
        "last_login": usage_stats["last_login"],
        "created_at": usage_stats["created_at"],
        "service_type": "TTS Reader"
    }

# WebSocket endpoint for real-time extraction progress
@app.websocket("/ws/extract/{extraction_id}")
async def websocket_extraction_progress(websocket: WebSocket, extraction_id: str):
    """WebSocket endpoint for real-time TTS extraction progress updates"""
    await websocket.accept()
    
    try:
        while True:
            if extraction_id in extraction_progress:
                progress_list = extraction_progress[extraction_id]
                if progress_list:
                    latest = progress_list[-1]
                    await websocket.send_text(json.dumps({
                        "status": latest.status,
                        "message": latest.message,
                        "progress": latest.progress,
                        "method": latest.method,
                        "timestamp": latest.timestamp.isoformat(),
                        "service": "TTS Content Extraction"
                    }))
                    
                    # Close connection if extraction is complete
                    if latest.status in ["completed", "failed"]:
                        break
            
            await asyncio.sleep(1)  # Update every second
            
    except Exception as e:
        logger.error(f"WebSocket error for extraction {extraction_id}: {str(e)}")
    finally:
        await websocket.close()

# Admin endpoints (for debugging - remove in production)
@app.post("/api/create-test-user")
async def create_test_user(db: Session = Depends(get_db)):
    """Create a test user for development"""
    try:
        # Check if test user already exists
        existing_user = db.query(User).filter(User.username == "testuser").first()
        if existing_user:
            return {"message": "Test user already exists", "username": "testuser"}
        
        # Create test user
        test_user = User(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User"
        )
        test_user.set_password("password123")
        
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        return {
            "message": "Test user created successfully",
            "username": "testuser",
            "password": "password123",
            "email": "test@example.com"
        }
    except Exception as e:
        logger.error(f"Error creating test user: {str(e)}")
        db.rollback()
        return {"error": str(e)}

@app.get("/api/admin/users")
async def list_users(db: Session = Depends(get_db)):
    """List all users (admin only - add proper authorization)"""
    users = db.query(User).all()
    return {
        "total_users": len(users),
        "users": [
            {
                "user_id": str(user.user_id),
                "username": user.username,
                "email": user.email,
                "remaining_chars": user.remaining_chars,
                "is_active": user.is_active,
                "created_at": user.created_at
            }
            for user in users
        ]
    }

@app.get("/api/admin/database/status")
async def database_status():
    """Get database status information"""
    return await db_health_check()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
        workers=1  # Use 1 for development, increase for production
    )