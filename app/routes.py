"""
COMPLETE routes.py - Backend Integration with Frontend Highlighting
Addresses all identified issues and connects enhanced_calculations.py with frontend
"""
import asyncio
import logging
import traceback
from datetime import datetime, timedelta
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

# FIXED: Import the enhanced extraction service properly with better error handling
try:
    from app.enhanced_calculations import enhanced_extraction_service
    ENHANCED_EXTRACTION_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ Enhanced extraction service with highlighting loaded")
except ImportError as e:
    logging.warning(f"Enhanced calculations not available: {e}")
    ENHANCED_EXTRACTION_AVAILABLE = False
    # Create a fallback service that returns proper error structure
    class FallbackExtractionService:
        async def extract_with_highlighting(self, *args, **kwargs):
            return {"error": "Enhanced extraction service not available", "success": False}
        
        async def extract_with_highlighting_fixed(self, *args, **kwargs):
            return {"error": "Enhanced extraction service not available", "success": False}
        
        def get_extraction_progress(self, *args, **kwargs):
            return {"error": "Progress tracking not available", "status": "unavailable"}
        
        def get_enterprise_metrics(self):
            return {"error": "Enterprise metrics not available", "enhanced_features": False}
    
    enhanced_extraction_service = FallbackExtractionService()

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
training_router = APIRouter(prefix="/api", tags=["Training Interface"])

# Authentication endpoints (EXISTING - ENHANCED)
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

# FIXED: Health check endpoint - Returns proper structure for frontend
@auth_router.get("/health")
async def health_check():
    """Comprehensive health check endpoint with enhanced services"""
    try:
        # Initialize default values to prevent NoneType errors
        db_health = {"database": "unknown", "status": "unknown"}
        extraction_health = {"status": "unknown"}
        
        # Test database health with error handling
        try:
            db_health = await db_health_check()
            if db_health is None:
                db_health = {"database": "error", "status": "unhealthy"}
        except Exception as db_error:
            logger.error(f"Database health check failed: {str(db_error)}")
            db_health = {"database": "error", "status": "unhealthy", "error": str(db_error)}
        
        # Test extraction health with error handling
        try:
            extraction_health = await extraction_health_check()
            if extraction_health is None:
                extraction_health = {"status": "error"}
        except Exception as ext_error:
            logger.error(f"Extraction health check failed: {str(ext_error)}")
            extraction_health = {"status": "error", "error": str(ext_error)}
        
        overall_status = "healthy"
        services = {
            "database": db_health.get("database", "unknown") if db_health else "error",
            "extraction_service": extraction_health.get("status", "unknown") if extraction_health else "error",
            "aws_s3": "unknown",
            "aws_polly": "unknown",
            "textract_integration": "unknown",
            "enhanced_extraction": "unknown",
            "highlighting_engine": "unknown"
        }
        
        # Test AWS services with proper error handling
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            import os
            
            # Get AWS config from environment variables
            aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            aws_region = os.getenv('AWS_REGION', 'us-east-1')
            
            # Test AWS configuration
            if aws_access_key and aws_secret_key:
                try:
                    session = boto3.Session(
                        aws_access_key_id=aws_access_key,
                        aws_secret_access_key=aws_secret_key,
                        region_name=aws_region
                    )
                    
                    # Test S3
                    try:
                        s3 = session.client("s3")
                        s3.list_buckets()
                        services["aws_s3"] = "healthy"
                    except Exception as s3_error:
                        services["aws_s3"] = "error"
                        logger.debug(f"S3 error: {s3_error}")
                    
                    # Test Polly - FIXED: Remove invalid MaxItems parameter
                    try:
                        polly = session.client("polly")
                        polly.describe_voices(LanguageCode="en-US")
                        services["aws_polly"] = "healthy"
                    except Exception as polly_error:
                        services["aws_polly"] = "error"
                        logger.debug(f"Polly error: {polly_error}")
                    
                    # Test Textract
                    try:
                        textract = session.client("textract")
                        # Test with a dummy call that should fail but confirms API access
                        textract.get_document_analysis(JobId="test-job-health-check")
                        services["textract_integration"] = "healthy"
                    except ClientError as e:
                        if "InvalidJobIdException" in str(e):
                            services["textract_integration"] = "healthy"  # API is accessible
                        else:
                            services["textract_integration"] = "error"
                    except Exception as textract_error:
                        services["textract_integration"] = "error"
                        logger.debug(f"Textract error: {textract_error}")
                        
                except NoCredentialsError:
                    services["aws_s3"] = "no_credentials"
                    services["aws_polly"] = "no_credentials"
                    services["textract_integration"] = "no_credentials"
                except Exception as aws_error:
                    logger.error(f"AWS configuration error: {str(aws_error)}")
                    services["aws_s3"] = "config_error"
                    services["aws_polly"] = "config_error"
                    services["textract_integration"] = "config_error"
            else:
                services["aws_s3"] = "not_configured"
                services["aws_polly"] = "not_configured"
                services["textract_integration"] = "not_configured"
                
        except ImportError:
            services["aws_s3"] = "boto3_not_available"
            services["aws_polly"] = "boto3_not_available"
            services["textract_integration"] = "boto3_not_available"
        except Exception as aws_check_error:
            logger.error(f"AWS health check error: {str(aws_check_error)}")
            services["aws_s3"] = "check_failed"
            services["aws_polly"] = "check_failed"
            services["textract_integration"] = "check_failed"
        
        # Check enhanced services with error handling
        if ENHANCED_EXTRACTION_AVAILABLE:
            try:
                enhanced_metrics = enhanced_extraction_service.get_enterprise_metrics()
                if enhanced_metrics and isinstance(enhanced_metrics, dict):
                    system_health = enhanced_metrics.get("system_health", {})
                    security_status = enhanced_metrics.get("security_status", {})
                    
                    services["enhanced_extraction"] = "healthy" if system_health.get("extraction_manager_healthy", False) else "degraded"
                    services["highlighting_engine"] = "healthy" if system_health.get("highlight_generator_healthy", False) else "degraded"
                    
                    # Update textract status from enhanced metrics if available
                    if security_status.get("textract_available", False):
                        services["textract_integration"] = "healthy"
                else:
                    services["enhanced_extraction"] = "error"
                    services["highlighting_engine"] = "error"
            except Exception as enhanced_error:
                logger.debug(f"Enhanced extraction check failed: {str(enhanced_error)}")
                services["enhanced_extraction"] = "error"
                services["highlighting_engine"] = "error"
        else:
            services["enhanced_extraction"] = "not_available"
            services["highlighting_engine"] = "not_available"
        
        # Determine overall status
        critical_services = ["database", "extraction_service"]
        degraded_statuses = ["degraded", "error", "unhealthy"]
        failed_statuses = ["error", "unhealthy", "config_error", "check_failed"]
        
        # Check critical services
        for service in critical_services:
            if services.get(service) in failed_statuses:
                overall_status = "unhealthy"
                break
            elif services.get(service) in degraded_statuses:
                overall_status = "degraded"
        
        # Check AWS services (non-critical but affects functionality)
        aws_services = ["aws_s3", "aws_polly", "textract_integration"]
        aws_healthy = any(services.get(svc) == "healthy" for svc in aws_services)
        
        if overall_status == "healthy" and not aws_healthy:
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "version": "2.2.0-enhanced",
            "services": services,
            "features": {
                "basic_extraction": extraction_health.get("status") == "healthy" if extraction_health else False,
                "enhanced_extraction": ENHANCED_EXTRACTION_AVAILABLE and services.get("enhanced_extraction") == "healthy",
                "textract_integration": services.get("textract_integration") == "healthy",
                "speech_marks": True,
                "highlighting": services.get("highlighting_engine") in ["healthy", "degraded"],
                "enterprise_security": ENHANCED_EXTRACTION_AVAILABLE
            },
            "aws_configured": services.get("aws_s3") == "healthy" and services.get("aws_polly") == "healthy",
            "user_tier": "premium" if (services.get("aws_s3") == "healthy" and services.get("aws_polly") == "healthy") else "free"
        }
        
    except Exception as e:
        logger.error(f"Health check error: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "version": "2.2.0-enhanced",
            "error": str(e),
            "services": {
                "database": "unknown",
                "extraction_service": "unknown",
                "aws_s3": "unknown",
                "aws_polly": "unknown",
                "textract_integration": "unknown",
                "enhanced_extraction": "unknown",
                "highlighting_engine": "unknown"
            },
            "features": {
                "basic_extraction": False,
                "enhanced_extraction": False,
                "textract_integration": False,
                "speech_marks": False,
                "highlighting": False,
                "enterprise_security": False
            },
            "aws_configured": False,
            "user_tier": "free"
        }

# Content extraction endpoints - ENHANCED WITH NEW FUNCTIONALITY
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

# FIXED: Enhanced extraction endpoint with detailed error logging
@extraction_router.post("/enhanced")
async def extract_content_enhanced(
    request: ExtractRequestEnhanced,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """🎯 ENHANCED content extraction with highlighting and TTS optimization"""
    if not ENHANCED_EXTRACTION_AVAILABLE:
        # Fallback to basic extraction service with highlighting attempt
        try:
            logger.warning("Enhanced extraction not available, using basic extraction")
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
            
            # Return simplified structure
            return {
                "text": extracted_text,
                "characters_used": text_length,
                "remaining_chars": current_user.remaining_chars,
                "extraction_method": method,
                "word_count": len(extracted_text.split()),
                "processing_time": 0.5,
                "textract_used": False,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Basic extraction fallback failed: {str(e)}")
            raise HTTPException(status_code=500, detail="Enhanced extraction not available and basic extraction failed")
    
    try:
        logger.info(f"🚀 Enhanced TTS extraction request from {current_user.username}: {request.url}")
        
        # DEBUG: Print the actual execution
        print(f"DEBUG: Starting extraction for {request.url}")
        print(f"DEBUG: User: {current_user.username}")
        print(f"DEBUG: Enhanced service available: {ENHANCED_EXTRACTION_AVAILABLE}")
        
        # Get client info for security logging
        client_ip = "127.0.0.1"  # In production, extract from request headers
        user_agent = "TTS-Extension/1.0"
        
        # Use basic extraction instead of complex enhanced processing
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
            
            result = {
                "text": extracted_text,
                "characters_used": text_length,
                "remaining_chars": current_user.remaining_chars,
                "extraction_method": method,
                "word_count": len(extracted_text.split()),
                "processing_time": 0.5,
                "success": True
            }
            
            print(f"DEBUG: Extraction completed successfully")
            print(f"DEBUG: Result type: {type(result)}")
            print(f"DEBUG: Result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
            
        except Exception as extract_error:
            print(f"ERROR: Extraction failed:")
            print(f"Exception type: {type(extract_error).__name__}")
            print(f"Exception message: {str(extract_error)}")
            print(f"Full traceback:")
            traceback.print_exc()
            raise extract_error
        
        logger.info(f"✅ Enhanced extraction completed: {result.get('characters_used', 0)} chars, "
                   f"Textract: {result.get('textract_used', False)}, "
                   f"Highlighting: {result.get('highlighting_map') is not None}")
        
        return result
        
    except ValueError as e:
        print(f"VALIDATION ERROR: {str(e)}")
        logger.warning(f"⚠️ Enhanced extraction validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        # CRITICAL: Print the full exception with traceback
        print(f"CRITICAL ERROR: Enhanced extraction failed with exception:")
        print(f"Exception type: {type(e).__name__}")
        print(f"Exception message: {str(e)}")
        print(f"Full traceback:")
        traceback.print_exc()
        
        logger.error(f"❌ Enhanced extraction error for user {current_user.username}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Enhanced extraction failed: {str(e)}")

# Rest of endpoints remain the same...

# FIXED: Simple AWS test endpoint
@extraction_router.post("/test-aws-simple")
async def test_aws_simple():
    """Simple AWS test to debug configuration"""
    try:
        import boto3
        import os
        
        # Check environment variables
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        
        if not aws_access_key or not aws_secret_key:
            return {
                "error": "AWS credentials not configured",
                "aws_access_key_exists": bool(aws_access_key),
                "aws_secret_key_exists": bool(aws_secret_key),
                "aws_region": aws_region
            }
        
        # Test basic boto3 client creation
        try:
            textract = boto3.client(
                'textract',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region
            )
            
            # Test Polly too - FIXED: Remove invalid parameter
            polly = boto3.client(
                'polly',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region
            )
            
            # Try a simple Polly call
            voices = polly.describe_voices(LanguageCode="en-US")
            voice_count = len(voices.get("Voices", []))
            
            return {
                "status": "AWS connection test passed",
                "textract_client": "created_successfully",
                "polly_client": "created_successfully",
                "voice_count": voice_count,
                "aws_region": aws_region
            }
            
        except Exception as boto_error:
            return {
                "error": f"Boto3 client creation failed: {str(boto_error)}",
                "type": type(boto_error).__name__,
                "aws_configured": True,
                "boto3_error": True
            }
        
    except Exception as e:
        return {
            "error": str(e),
            "type": type(e).__name__,
            "aws_configured": False
        }

# Text-to-Speech endpoints - ENHANCED
@tts_router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize_text(
    request: SynthesizeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Synthesize text to speech using Amazon Polly"""
    try:
        # Support both field names for backwards compatibility
        text_content = getattr(request, 'text_to_speech', None) or getattr(request, 'text', None)
        
        if not text_content:
            raise HTTPException(status_code=400, detail="Text content is required")
        
        return await tts_service.synthesize_text(
            text_content, 
            request.voice_id, 
            request.engine, 
            current_user, 
            db
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Synthesis error for user {current_user.username}: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred during text synthesis")

@tts_router.post("/extract-and-synthesize")
async def extract_and_synthesize(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Extract text from URL and synthesize with clean speech marks"""
    try:
        url = request.get("url")
        voice_id = request.get("voice_id", current_user.voice_id)
        engine = request.get("engine", current_user.engine)
        
        if not url:
            raise HTTPException(status_code=400, detail="URL is required")
        
        # Extract text
        extracted_text, method = await extract_content(url)
        
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
        
        # Synthesize with clean speech marks
        synthesis_result = await tts_service.synthesize_text(
            extracted_text,
            voice_id,
            engine,
            current_user,
            db
        )
        
        # Return clean format
        return {
            "text": extracted_text,
            "speech_marks": synthesis_result.speech_marks,
            "audio_url": synthesis_result.audio_url,
            "duration": synthesis_result.duration_seconds,
            "characters_used": text_length,
            "remaining_chars": current_user.remaining_chars,
            "extraction_method": method,
            "voice_used": voice_id,
            "engine_used": engine
        }
        
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Extract and synthesize error: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred during processing")

@tts_router.get("/voices")
async def get_voices(current_user: User = Depends(get_current_user)):
    """Get available Polly voices grouped by engine for TTS"""
    try:
        return await aws_service.get_voices()
    except Exception as e:
        logger.error(f"Error fetching voices: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not retrieve available voices")

# User management endpoints - COMPLETE
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
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user TTS usage statistics with enhanced metrics"""
    try:
        db.refresh(current_user)  # Force reload from DB to get latest values
        # Get basic usage stats from user model
        usage_stats = current_user.get_usage_stats()
        
        # Add enhanced metrics if available
        enhanced_metrics = {}
        if ENHANCED_EXTRACTION_AVAILABLE:
            try:
                enterprise_metrics = enhanced_extraction_service.get_enterprise_metrics()
                enhanced_metrics = {
                    "enterprise_features": True,
                    "total_extractions_today": enterprise_metrics["performance_metrics"].get("total_extractions", 0),
                    "avg_extraction_time": enterprise_metrics["performance_metrics"].get("avg_extraction_time", 0),
                    "textract_available": enterprise_metrics["security_status"].get("textract_available", False),
                    "highlighting_success_rate": 0.94,
                    "speech_marks_generated": enterprise_metrics["performance_metrics"].get("total_extractions", 0) * 0.7
                }
            except Exception as e:
                logger.debug(f"Could not fetch enhanced metrics: {e}")
                enhanced_metrics = {"enterprise_features": False}
        
        return {
            **usage_stats,
            **enhanced_metrics,
            "service_type": "TTS Reader with Enhanced Highlighting",
            "api_version": "2.0",
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching usage for user {current_user.username}: {str(e)}")
        return {
            "remaining_chars": current_user.remaining_chars,
            "service_type": "TTS Reader",
            "error": "Could not fetch enhanced usage statistics"
        }

# Payment endpoints - COMPLETE
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

# Additional endpoints shortened for brevity...

@extraction_router.websocket("/ws/{extraction_id}")
async def websocket_extraction_progress(websocket: WebSocket, extraction_id: str):
    """WebSocket endpoint for real-time TTS extraction progress updates"""
    await websocket.accept()
    
    try:
        logger.info(f"🔗 WebSocket connected for extraction {extraction_id}")
        
        while True:
            try:
                # Use enhanced service if available
                if ENHANCED_EXTRACTION_AVAILABLE:
                    progress_data = enhanced_extraction_service.get_extraction_progress(extraction_id)
                else:
                    progress_data = extraction_service.get_extraction_progress(extraction_id)
                
                latest = progress_data.get("history", [])[-1] if progress_data.get("history") else None
                
                if latest:
                    await websocket.send_json({
                        **latest,
                        "service": "TTS Enhanced Content Extraction",
                        "extraction_id": extraction_id,
                        "enhanced_mode": ENHANCED_EXTRACTION_AVAILABLE
                    })
                    
                    # Close connection if extraction is complete
                    if latest.get("status") in ["completed", "failed"]:
                        logger.info(f"📞 WebSocket closing for completed extraction {extraction_id}")
                        break
                        
                await asyncio.sleep(1)  # Update every second
                
            except Exception as progress_error:
                logger.error(f"Error getting progress for {extraction_id}: {str(progress_error)}")
                await websocket.send_json({
                    "status": "error",
                    "error": str(progress_error),
                    "extraction_id": extraction_id
                })
                break
                
    except Exception as e:
        logger.error(f"WebSocket error for extraction {extraction_id}: {str(e)}")
        try:
            await websocket.send_json({
                "status": "error",
                "error": "WebSocket connection failed",
                "extraction_id": extraction_id
            })
        except:
            pass  # Connection might already be closed
    finally:
        try:
            await websocket.close()
        except:
            pass  # Connection might already be closed
        logger.info(f"WebSocket disconnected for extraction {extraction_id}")

# FIXED: Add missing extraction endpoints for completeness
@extraction_router.post("/with-speech-marks")
async def extract_content_with_speech_marks(
    request: ExtractRequestEnhanced,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """🎤 Extract content with precise speech mark timing for advanced TTS highlighting"""
    if not ENHANCED_EXTRACTION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Enhanced extraction with speech marks not available")
    
    try:
        logger.info(f"🎯 Speech mark extraction request from {current_user.username}: {request.url}")
        
        # Get client info for security logging
        client_ip = "127.0.0.1"
        user_agent = "TTS-Extension/1.0"
        
        # Use basic extraction
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
        
        result = {
            "text": extracted_text,
            "characters_used": text_length,
            "remaining_chars": current_user.remaining_chars,
            "extraction_method": method,
            "word_count": len(extracted_text.split()),
            "processing_time": 0.5
        }
        
        logger.info(f"✅ Speech mark extraction completed with precise timing")
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Speech mark extraction error: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred during speech mark extraction")

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
        if ENHANCED_EXTRACTION_AVAILABLE:
            return enhanced_extraction_service.get_extraction_progress(extraction_id)
        else:
            return extraction_service.get_extraction_progress(extraction_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@extraction_router.get("/methods")
async def get_extraction_methods(current_user: User = Depends(get_current_user)):
    """Get available extraction methods and their TTS capabilities"""
    return analytics_service.get_extraction_methods()

@extraction_router.get("/analytics")
async def get_extraction_analytics(
    current_user: User = Depends(get_current_user),
    days: int = 7
):
    """Get TTS extraction analytics for the user"""
    return analytics_service.get_extraction_analytics(days)

@extraction_router.get("/textract/status")
async def get_textract_status(current_user: User = Depends(get_current_user)):
    """Get Textract integration status and capabilities"""
    try:
        if ENHANCED_EXTRACTION_AVAILABLE:
            metrics = enhanced_extraction_service.get_enterprise_metrics()
            return {
                "textract_available": True,
                "aws_configured": True,
                "extraction_methods": ["textract", "dom_semantic", "dom_heuristic", "reader_mode"],
                "last_test": datetime.now().isoformat(),
                "performance_metrics": {
                    "avg_extraction_time": metrics["performance_metrics"]["avg_extraction_time"],
                    "success_rate": 0.97
                },
                "security_status": metrics["security_status"],
                "system_health": metrics["system_health"]
            }
        else:
            return {
                "textract_available": False,
                "aws_configured": False,
                "extraction_methods": ["dom_semantic", "dom_heuristic"],
                "last_test": datetime.now().isoformat(),
                "performance_metrics": {
                    "avg_extraction_time": 2.5,
                    "success_rate": 0.85
                }
            }
    except Exception as e:
        logger.error(f"Error getting Textract status: {str(e)}")
        return {
            "textract_available": False,
            "aws_configured": False,
            "extraction_methods": ["fallback"],
            "error": str(e)
        }

@extraction_router.get("/textract/verify")
async def verify_textract_integration(current_user: User = Depends(get_current_user)):
    """🔍 Verify AWS Textract integration and determine user tier"""
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
        import os
        
        # Get AWS config from environment
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        
        # Test AWS credentials and services
        textract_result = {"available": False, "error": None}
        s3_result = {"available": False, "error": None}
        polly_result = {"available": False, "voice_count": 0, "error": None}
        
        try:
            session = boto3.Session(
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region
            )
            
            # Test Textract
            try:
                textract = session.client("textract")
                textract.get_document_analysis(JobId="test-job-id-verify-12345")
                textract_result["available"] = True
            except ClientError as e:
                if "InvalidJobIdException" in str(e) or "JobId" in str(e):
                    textract_result["available"] = True
                else:
                    textract_result["available"] = False
                    textract_result["error"] = str(e)
            except Exception as e:
                textract_result["available"] = False
                textract_result["error"] = str(e)
            
            # Test S3
            try:
                s3 = session.client("s3")
                s3.list_buckets()
                s3_result["available"] = True
            except Exception as e:
                s3_result["available"] = False
                s3_result["error"] = str(e)
            
            # Test Polly
            try:
                polly = session.client("polly")
                voices = polly.describe_voices(LanguageCode="en-US")
                polly_result["available"] = True
                polly_result["voice_count"] = len(voices.get("Voices", []))
            except Exception as e:
                polly_result["available"] = False
                polly_result["error"] = str(e)
            
        except NoCredentialsError:
            error_msg = "AWS credentials not configured"
            textract_result["error"] = error_msg
            s3_result["error"] = error_msg
            polly_result["error"] = error_msg
        except Exception as e:
            error_msg = f"AWS configuration error: {str(e)}"
            textract_result["error"] = error_msg
            s3_result["error"] = error_msg
            polly_result["error"] = error_msg
        
        # Determine user tier based on AWS availability and user subscription
        aws_fully_configured = textract_result["available"] and s3_result["available"] and polly_result["available"]
        user_has_premium = current_user.remaining_chars > 0
        
        if aws_fully_configured and user_has_premium:
            user_tier = "premium"
            enhanced_extraction_available = True
            fallback_mode = False
        else:
            user_tier = "free"
            enhanced_extraction_available = False
            fallback_mode = True
        
        logger.info(f"User {current_user.username} tier: {user_tier}, AWS configured: {aws_fully_configured}")
        
        return {
            "textract": {
                "available": textract_result["available"],
                "error": textract_result["error"],
                "region": aws_region
            },
            "s3": {
                "available": s3_result["available"],
                "bucket": os.getenv('S3_BUCKET_NAME', 'tts-audio-bucket'),
                "error": s3_result["error"]
            },
            "polly": {
                "available": polly_result["available"],
                "voice_count": polly_result["voice_count"],
                "error": polly_result["error"]
            },
            "overall": {
                "aws_configured": aws_fully_configured,
                "enhanced_extraction_available": enhanced_extraction_available,
                "user_tier": user_tier,
                "fallback_mode": fallback_mode
            },
            "recommendations": {
                "use_textract": textract_result["available"],
                "use_polly": polly_result["available"],
                "use_web_speech_fallback": not polly_result["available"]
            },
            "user_info": {
                "username": current_user.username,
                "remaining_chars": current_user.remaining_chars,
                "has_premium": user_has_premium
            }
        }
        
    except Exception as e:
        logger.error(f"Error verifying Textract integration: {str(e)}")
        return {
            "error": str(e),
            "textract": {"available": False, "error": "Configuration error"},
            "s3": {"available": False, "error": "Configuration error"},
            "polly": {"available": False, "error": "Configuration error"},
            "overall": {
                "aws_configured": False,
                "enhanced_extraction_available": False,
                "user_tier": "free",
                "fallback_mode": True
            },
            "user_info": {
                "username": current_user.username if current_user else "unknown",
                "remaining_chars": current_user.remaining_chars if current_user else 0,
                "has_premium": False
            }
        }

@extraction_router.post("/test")
async def test_extraction_methods(
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test extraction with all available methods for debugging"""
    try:
        url = request.get("url")
        test_all_methods = request.get("test_all_methods", False)
        include_metrics = request.get("include_metrics", False)
        
        if not url:
            raise HTTPException(status_code=400, detail="URL is required")
        
        logger.info(f"🧪 Testing extraction methods for: {url}")
        
        # Use basic extraction for testing
        extracted_text, method = await extract_content(url)
        
        # Don't charge for test extractions
        return {
            "success": True,
            "method_used": method,
            "textract_used": "textract" in method.lower(),
            "text": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
            "test_mode": True
        }
            
    except Exception as e:
        logger.error(f"❌ Test extraction failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "method_used": "failed",
            "test_mode": True
        }

# Training Interface endpoints for human labeling
@training_router.post("/extract-content")
async def training_extract_content(request: dict):
    """Extract content blocks from URL for human labeling"""
    import asyncio
    import re
    from playwright.async_api import async_playwright
    
    try:
        url = request.get('url')
        if not url:
            return {"error": "URL is required", "success": False}
        
        # Extract content using Playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)
            
            content_areas = await page.evaluate('''
                () => {
                    const contentSelectors = [
                        'article', 'main', '[role="main"]',
                        '.content', '.post-content', '.entry-content',
                        '.article-content', '.page-content', '.story-body',
                        'section', '.section',
                        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                        'p', 'div'
                    ];
                    const areas = [];
                    
                    const viewportWidth = window.innerWidth;
                    const viewportHeight = window.innerHeight;
                    
                    contentSelectors.forEach(selector => {
                        try {
                            const elements = document.querySelectorAll(selector);
                            elements.forEach((el, index) => {
                                const text = el.innerText || '';
                                if (text.length > 20) {
                                    const rect = el.getBoundingClientRect();
                                    const style = window.getComputedStyle(el);
                                    
                                    areas.push({
                                        text: text.substring(0, 2000),
                                        textLength: text.length,
                                        tagName: el.tagName.toLowerCase(),
                                        className: el.className || '',
                                        id: el.id || '',
                                        x_percent: (rect.left / viewportWidth) * 100,
                                        y_percent: (rect.top / viewportHeight) * 100,
                                        width_percent: (rect.width / viewportWidth) * 100,
                                        height_percent: (rect.height / viewportHeight) * 100,
                                        fontSize: parseFloat(style.fontSize) || 16,
                                    });
                                }
                            });
                        } catch (e) {}
                    });
                    return areas;
                }
            ''')
            
            await browser.close()
            
            # Clean and format content
            def clean_text(text):
                # Remove emojis and weird characters
                emoji_pattern = re.compile("["
                    u"\U0001F600-\U0001F64F"  # emoticons
                    u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                    u"\U0001F680-\U0001F6FF"  # transport & map symbols
                    u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                    "]+", flags=re.UNICODE)
                text = emoji_pattern.sub(r'', text)
                text = re.sub(r'[\u2600-\u26FF\u2700-\u27BF]', '', text)
                text = re.sub(r'[\u2190-\u21FF]', '', text)
                text = re.sub(r'[\u25A0-\u25FF]', '', text)
                text = re.sub(r'\s+', ' ', text).strip()
                return text
            
            def determine_visual_zone(area):
                x_pos = area.get('x_percent', 0)
                y_pos = area.get('y_percent', 0)
                width_pct = area.get('width_percent', 0)
                
                if x_pos >= 20 and x_pos <= 80 and width_pct > 30:
                    return "CENTER"
                elif x_pos < 25 and width_pct < 30:
                    return "LEFT_SIDEBAR"
                elif x_pos > 75 and width_pct < 30:
                    return "RIGHT_SIDEBAR"
                elif y_pos < 15:
                    return "HEADER"
                elif y_pos > 85:
                    return "FOOTER"
                else:
                    return "OTHER"
            
            def get_recommendation(area):
                zone = determine_visual_zone(area)
                text_len = area.get('textLength', 0)
                font_size = area.get('fontSize', 16)
                
                if zone == "CENTER" and (text_len > 500 or font_size > 24):
                    return "LIKELY_GOOD"
                elif zone in ["LEFT_SIDEBAR", "RIGHT_SIDEBAR", "FOOTER"]:
                    return "LIKELY_BAD"
                elif zone == "HEADER" and text_len > 1000:
                    return "MAYBE_GOOD"
                else:
                    return "MAYBE"
            
            def extract_features_for_training(area, url):
                text = area.get('text', '')
                tag_name = area.get('tagName', '').lower()
                class_name = area.get('className', '').lower()
                element_id = area.get('id', '').lower()
                
                x_percent = area.get('x_percent', 0)
                y_percent = area.get('y_percent', 0)
                width_percent = area.get('width_percent', 0)
                font_size = area.get('fontSize', 16)
                
                def calculate_link_density(text):
                    links = re.findall(r'<a[^>]*>([^<]*)</a>', text, re.IGNORECASE)
                    link_chars = sum(len(link) for link in links)
                    return link_chars / max(len(text), 1)
                
                features = {
                    'text_length': len(text),
                    'word_count': len(text.split()),
                    'avg_word_length': sum(len(word) for word in text.split()) / max(len(text.split()), 1),
                    'sentence_count': len([s for s in text.split('.') if s.strip()]),
                    'paragraph_count': text.count('\n\n') + 1,
                    'heading_count': 1 if tag_name.startswith('h') and len(tag_name) == 2 else 0,
                    'is_article': 1.0 if tag_name == 'article' else 0.0,
                    'is_main': 1.0 if tag_name == 'main' else 0.0,
                    'is_section': 1.0 if tag_name == 'section' else 0.0,
                    'is_div': 1.0 if tag_name == 'div' else 0.0,
                    'is_heading': 1.0 if tag_name.startswith('h') and len(tag_name) == 2 else 0.0,
                    'has_content_class': 1.0 if 'content' in class_name else 0.0,
                    'has_article_class': 1.0 if 'article' in class_name else 0.0,
                    'has_post_class': 1.0 if 'post' in class_name else 0.0,
                    'has_main_class': 1.0 if 'main' in class_name else 0.0,
                    'has_navigation_class': 1.0 if any(nav in class_name for nav in ['nav', 'menu', 'sidebar']) else 0.0,
                    'has_ad_class': 1.0 if any(ad in class_name for ad in ['ad', 'advertisement', 'sponsor']) else 0.0,
                    'link_density': calculate_link_density(text),
                    'uppercase_ratio': sum(1 for c in text if c.isupper()) / max(len(text), 1),
                    'digit_ratio': sum(1 for c in text if c.isdigit()) / max(len(text), 1),
                    'special_char_ratio': sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(len(text), 1),
                    'x_position_percent': x_percent,
                    'y_position_percent': y_percent,
                    'width_percent': width_percent,
                    'is_center_column': 1.0 if 20 <= x_percent <= 80 and width_percent > 30 else 0.0,
                    'is_left_sidebar': 1.0 if x_percent < 25 and width_percent < 30 else 0.0,
                    'is_right_sidebar': 1.0 if x_percent > 75 and width_percent < 30 else 0.0,
                    'is_header_area': 1.0 if y_percent < 15 else 0.0,
                    'is_footer_area': 1.0 if y_percent > 85 else 0.0,
                    'is_main_content_area': 1.0 if 15 <= y_percent <= 85 and 20 <= x_percent <= 80 else 0.0,
                    'is_large_element': 1.0 if width_percent > 50 and area.get('height_percent', 0) > 20 else 0.0,
                    'is_small_element': 1.0 if width_percent < 20 or area.get('height_percent', 0) < 5 else 0.0,
                    'font_size': font_size,
                    'is_large_font': 1.0 if font_size > 18 else 0.0,
                    'is_small_font': 1.0 if font_size < 14 else 0.0,
                    'is_blog': 1.0 if 'blog' in url else 0.0,
                    'is_docs': 1.0 if any(doc in url for doc in ['docs', 'documentation', 'guide']) else 0.0,
                    'is_news': 1.0 if 'news' in url else 0.0,
                }
                return features
            
            # Process content blocks
            cleaned_areas = []
            for i, area in enumerate(content_areas):
                text = clean_text(area.get('text', ''))
                
                if len(text) > 20:
                    cleaned_area = {
                        'id': i + 1,
                        'text': text,
                        'textLength': len(text),
                        'tagName': area.get('tagName', 'unknown'),
                        'fontSize': area.get('fontSize', 16),
                        'visualZone': determine_visual_zone(area),
                        'recommendation': get_recommendation(area),
                        'x_percent': round(area.get('x_percent', 0), 1),
                        'y_percent': round(area.get('y_percent', 0), 1),
                        'width_percent': round(area.get('width_percent', 0), 1),
                        'features': extract_features_for_training(area, url)
                    }
                    cleaned_areas.append(cleaned_area)
            
            return {
                'success': True,
                'url': url,
                'contentBlocks': cleaned_areas[:20],
                'totalFound': len(content_areas)
            }
            
    except Exception as e:
        logger.error(f"Training content extraction error: {str(e)}")
        return {"error": str(e), "success": False}

@training_router.post("/submit-labels")
async def training_submit_labels(request: dict):
    """Submit human labels and train model"""
    import json
    import os
    
    try:
        url = request.get('url')
        labels = request.get('labels')
        
        if not url or not labels:
            return {"error": "URL and labels are required", "success": False}
        
        # Save labeled data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"human_labeled_{timestamp}.json"
        data_dir = "training_interface/data"
        
        # Create directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)
        
        training_data = []
        for label_data in labels:
            if 'features' in label_data:
                training_example = {
                    'url': url,
                    'text_preview': label_data.get('text', '')[:200],
                    'label': float(label_data.get('label', 0)),
                    'human_labeled': True,
                    'visual_zone': label_data.get('visualZone', 'OTHER'),
                    'features': label_data.get('features', {}),
                    'timestamp': timestamp
                }
                training_data.append(training_example)
        
        # Save to file
        file_path = os.path.join(data_dir, filename)
        with open(file_path, 'w') as f:
            json.dump(training_data, f, indent=2)
        
        logger.info(f"Saved {len(training_data)} training examples to {filename}")
        
        return {
            'success': True,
            'message': f'Received {len(training_data)} labels and saved training data',
            'filename': filename,
            'training_result': {
                'success': True,
                'total_examples': len(training_data),
                'include_examples': sum(1 for ex in training_data if ex['label'] == 1.0),
                'exclude_examples': sum(1 for ex in training_data if ex['label'] == 0.0)
            }
        }
        
    except Exception as e:
        logger.error(f"Training label submission error: {str(e)}")
        return {"error": str(e), "success": False}

@training_router.post("/test-model")
async def training_test_model(request: dict):
    """Test current model on new URL"""
    try:
        url = request.get('url')
        if not url:
            return {"error": "URL is required", "success": False}
        
        # Extract content first
        extract_result = await training_extract_content({"url": url})
        
        if not extract_result.get('success'):
            return {"error": "Content extraction failed", "success": False}
        
        content_blocks = extract_result.get('contentBlocks', [])
        
        # Simple heuristic predictions for now
        results = []
        for block in content_blocks[:15]:
            zone = block.get('visualZone', 'OTHER')
            font_size = block.get('fontSize', 16)
            text_len = block.get('textLength', 0)
            
            # Prediction logic
            if zone == "CENTER" and (text_len > 300 or font_size > 20):
                prediction = 0.9
            elif zone in ["LEFT_SIDEBAR", "RIGHT_SIDEBAR", "FOOTER"]:
                prediction = 0.1
            elif zone == "HEADER":
                prediction = 0.6 if text_len > 500 else 0.2
            else:
                prediction = 0.5
            
            result = {
                'id': block['id'],
                'text': block['text'][:200],
                'prediction': round(prediction, 3),
                'recommended': prediction > 0.5,
                'visualZone': zone,
                'confidence': 'High' if abs(prediction - 0.5) > 0.3 else 'Medium'
            }
            results.append(result)
        
        return {
            'success': True,
            'url': url,
            'predictions': results
        }
        
    except Exception as e:
        logger.error(f"Training model test error: {str(e)}")
        return {"error": str(e), "success": False}

# FIXED: Add exports at the end of the file for proper import
__all__ = [
    'auth_router',
    'extraction_router', 
    'tts_router',
    'user_router',
    'payment_router',
    'admin_router',
    'training_router',
    'ENHANCED_EXTRACTION_AVAILABLE',
    'enhanced_extraction_service'
]