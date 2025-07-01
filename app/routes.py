"""
API routes for TTS Reader API
"""
import logging
from datetime import timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket
from sqlalchemy.orm import Session

from .auth import auth_manager, get_current_user, validate_user_registration, create_user_account
from .models import (
    UserCreate, UserLogin, UserResponse, Token, ExtractRequest, ExtractRequestEnhanced,
    ExtractResponse, ExtractResponseEnhanced, SynthesizeRequest, SynthesizeResponse,
    PreferencesUpdate, StripeCheckoutRequest, ExtractionPreview
)
from .services import (
    aws_service, extraction_service, tts_service, stripe_service, analytics_service
)
from database import get_db, health_check as db_health_check
from models import User
from textract_processor import extract_content, health_check as extraction_health_check

logger = logging.getLogger(__name__)

# Create routers for different endpoint groups
auth_router = APIRouter(prefix="/api", tags=["Authentication"])
extraction_router = APIRouter(prefix="/api/extract", tags=["Content Extraction"])
tts_router = APIRouter(prefix="/api", tags=["Text-to-Speech"])
user_router = APIRouter(prefix="/api", tags=["User Management"])
payment_router = APIRouter(prefix="/api", tags=["Payments"])
admin_router = APIRouter(prefix="/api/admin", tags=["Administration"])

# Authentication endpoints
@auth_router.post("/register", response_model=UserResponse)
async def register(request: Request, user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user with enhanced validation"""
    logger.info(f"Registration attempt for username: {user_data.username}")
    
    # Validate registration data
    validate_user_registration(user_data.username, user_data.email, db)
    
    # Create user account
    db_user = create_user_account(user_data.dict(), db)
    
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

@auth_router.post("/login", response_model=Token)
async def login(request: Request, user_data: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return access token"""
    logger.info(f"Login attempt for username: {user_data.username}")
    
    # Authenticate user
    db_user = auth_manager.authenticate_user(db, user_data.username, user_data.password)
    
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Update last login
    db_user.update_last_login()
    db.commit()
    
    # Create tokens
    access_token = auth_manager.create_access_token(data={"sub": db_user.username})
    refresh_token = auth_manager.create_refresh_token(db_user.username)
    
    logger.info(f"User {db_user.username} authenticated successfully")
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token
    )

@auth_router.post("/token", response_model=Token)
async def login_for_access_token(request: Request, user_data: UserLogin, db: Session = Depends(get_db)):
    """OAuth2 compatible token endpoint"""
    return await login(request, user_data, db)

# Content extraction endpoints
@extraction_router.post("", response_model=ExtractResponse)
async def extract_content_basic(
    request: ExtractRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Extract text content from URL (basic endpoint for backwards compatibility)"""
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
        raise HTTPException(status_code=500, detail="An error occurred during content extraction")

@extraction_router.post("/enhanced", response_model=ExtractResponseEnhanced)
async def extract_content_enhanced(
    request: ExtractRequestEnhanced,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Enhanced content extraction with progress tracking and metadata for TTS"""
    try:
        return await extraction_service.extract_content_enhanced(
            request.url, current_user, db, request.prefer_textract, request.include_metadata
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred during content extraction")

@extraction_router.post("/preview", response_model=ExtractionPreview)
async def extract_content_preview(
    request: ExtractRequest,
    current_user: User = Depends(get_current_user)
):
    """Get a preview of extracted TTS content without using character credits"""
    try:
        return await extraction_service.extract_preview(request.url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred during preview extraction")

@extraction_router.get("/progress/{extraction_id}")
async def get_extraction_progress(
    extraction_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get real-time progress of content extraction"""
    try:
        return extraction_service.get_extraction_progress(extraction_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@extraction_router.get("/methods")
async def get_extraction_methods(current_user: User = Depends(get_current_user)):
    """Get available extraction methods and their capabilities for TTS"""
    return analytics_service.get_extraction_methods()

@extraction_router.get("/analytics")
async def get_extraction_analytics(
    current_user: User = Depends(get_current_user),
    days: int = 7
):
    """Get TTS extraction analytics for the user"""
    return analytics_service.get_extraction_analytics(days)

# Text-to-Speech endpoints
@tts_router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize_text(
    request: SynthesizeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Synthesize text to speech using Amazon Polly with enhanced TTS processing"""
    try:
        return await tts_service.synthesize_text(
            request.text_to_speech, request.voice_id, request.engine, current_user, db
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred during text synthesis")

@tts_router.get("/voices")
async def get_voices(current_user: User = Depends(get_current_user)):
    """Get available Polly voices grouped by engine for TTS"""
    try:
        return await aws_service.get_voices()
    except Exception as e:
        logger.error(f"Error fetching voices: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not retrieve available voices")

# User management endpoints
@user_router.get("/user", response_model=UserResponse)
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

@user_router.get("/preferences")
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

@user_router.post("/preferences")
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
        raise HTTPException(status_code=500, detail="An error occurred while updating preferences")

@user_router.get("/usage")
async def get_usage(current_user: User = Depends(get_current_user)):
    """Get user TTS usage statistics"""
    usage_stats = current_user.get_usage_stats()
    return {
        **usage_stats,
        "service_type": "TTS Reader"
    }

# Payment endpoints
@payment_router.post("/create-checkout-session")
async def create_checkout_session(
    request: StripeCheckoutRequest,
    current_user: User = Depends(get_current_user)
):
    """Create a Stripe checkout session for subscription"""
    try:
        url = await stripe_service.create_checkout_session(request.price_id, current_user.username)
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

@payment_router.post("/stripe_webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    
    try:
        return stripe_service.handle_webhook_event(payload, sig_header, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Health check endpoint
@auth_router.get("/health")
async def health_check():
    """Comprehensive health check endpoint"""
    db_health = await db_health_check()
    extraction_health = await extraction_health_check()
    
    overall_status = "healthy"
    if db_health["database"] != "healthy" or extraction_health["status"] != "healthy":
        overall_status = "degraded"
    
    return {
        "status": overall_status,
        "timestamp": "2024-01-01T00:00:00Z",  # This would be dynamic
        "version": "2.2.0",
        "database": db_health,
        "extraction_service": extraction_health,
        "aws_s3": "healthy",
        "aws_polly": "healthy"
    }

# WebSocket endpoint for real-time extraction progress
@extraction_router.websocket("/ws/{extraction_id}")
async def websocket_extraction_progress(websocket: WebSocket, extraction_id: str):
    """WebSocket endpoint for real-time TTS extraction progress updates"""
    await websocket.accept()
    
    try:
        while True:
            try:
                progress_data = extraction_service.get_extraction_progress(extraction_id)
                latest = progress_data["history"][-1] if progress_data["history"] else None
                
                if latest:
                    await websocket.send_json({
                        **latest,
                        "service": "TTS Content Extraction"
                    })
                    
                    # Close connection if extraction is complete
                    if latest.get("status") in ["completed", "failed"]:
                        break
                        
                await asyncio.sleep(1)  # Update every second
                
            except ValueError:
                # Extraction ID not found
                break
                
    except Exception as e:
        logger.error(f"WebSocket error for extraction {extraction_id}: {str(e)}")
    finally:
        await websocket.close()

# Admin endpoints (for debugging - add proper authorization in production)
@admin_router.post("/create-test-user")
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

@admin_router.get("/users")
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

@admin_router.get("/database/status")
async def database_status():
    """Get database status information"""
    return await db_health_check()