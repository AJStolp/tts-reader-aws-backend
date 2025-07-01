"""
Pydantic models for TTS Reader API
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr

# User models
class UserCreate(BaseModel):
    """Model for user registration"""
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=6, max_length=128)
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=128)
    last_name: str = Field(..., min_length=1, max_length=128)

class UserLogin(BaseModel):
    """Model for user login"""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)

class UserResponse(BaseModel):
    """Model for user response data"""
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
    """Model for authentication tokens"""
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None

# Content extraction models
class ExtractRequest(BaseModel):
    """Basic extraction request model"""
    url: str = Field(..., pattern=r"^https?://.*")

class ExtractRequestEnhanced(BaseModel):
    """Enhanced extraction request with options"""
    url: str = Field(..., pattern=r"^https?://.*")
    prefer_textract: bool = Field(default=True, description="Whether to prefer Textract over DOM extraction")
    include_metadata: bool = Field(default=False, description="Whether to include extraction metadata")

class ExtractResponse(BaseModel):
    """Basic extraction response model"""
    text: str
    characters_used: int
    remaining_chars: int
    extraction_method: str

class ExtractResponseEnhanced(BaseModel):
    """Enhanced extraction response with metadata"""
    text: str
    characters_used: int
    remaining_chars: int
    extraction_method: str
    content_type: Optional[str] = None
    confidence: Optional[float] = None
    word_count: Optional[int] = None
    processing_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class ExtractionProgress(BaseModel):
    """Model for extraction progress updates"""
    status: str  # 'starting', 'processing', 'completed', 'failed'
    message: str
    progress: float  # 0.0 to 1.0
    method: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ExtractionPreview(BaseModel):
    """Model for content preview"""
    preview: str  # First 500 characters
    estimated_length: int
    confidence: float
    method: str
    content_type: Optional[str] = None
    tts_score: Optional[float] = None
    full_available: bool = True

# TTS synthesis models
class SynthesizeRequest(BaseModel):
    """Model for TTS synthesis request"""
    text_to_speech: str = Field(..., min_length=1, max_length=100000)
    voice_id: str = Field(default="Joanna", max_length=50)
    engine: str = Field(default="standard", pattern="^(standard|neural)$")

class SynthesizeResponse(BaseModel):
    """Model for TTS synthesis response"""
    audio_url: str
    speech_marks_url: str
    characters_used: int
    remaining_chars: int
    duration_seconds: float

# User preferences models
class PreferencesUpdate(BaseModel):
    """Model for updating user preferences"""
    engine: Optional[str] = Field(None, pattern="^(standard|neural)$")
    voice_id: Optional[str] = Field(None, max_length=50)

# Stripe models
class StripeCheckoutRequest(BaseModel):
    """Model for Stripe checkout session creation"""
    price_id: str = Field(default="price_1RcGYRQwS4m9kgMV6C1wAZcN")

# Health check models
class HealthCheckResponse(BaseModel):
    """Model for health check response"""
    status: str
    timestamp: str
    version: str
    database: Dict[str, Any]
    extraction_service: Dict[str, Any]
    aws_s3: str
    aws_polly: str

class ExtractionMethodInfo(BaseModel):
    """Model for extraction method information"""
    id: str
    name: str
    description: str
    speed: str
    accuracy: str
    tts_optimized: bool
    available: bool

class AnalyticsResponse(BaseModel):
    """Model for analytics response"""
    period_days: int
    total_extractions: int
    total_characters: int
    average_extraction_time: float
    tts_optimized_extractions: int
    methods_used: Dict[str, int]
    success_rate: float
    average_confidence: float
    most_common_sites: list
    content_types: Dict[str, int]

# Error models
class ErrorResponse(BaseModel):
    """Standard error response model"""
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))