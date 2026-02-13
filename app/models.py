"""
Pydantic models for TTS Reader API
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, EmailStr

# User models
class UserCreate(BaseModel):
    """Model for user registration"""
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=6, max_length=128)
    email: EmailStr
    first_name: Optional[str] = Field(default=None, max_length=128)
    last_name: Optional[str] = Field(default=None, max_length=128)

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
    content: Optional[str] = Field(default=None, description="Pre-extracted content to use instead of URL extraction")
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
    word_count: Optional[int] = None
    estimated_reading_time: Optional[float] = None

# TTS synthesis models
class SynthesizeRequest(BaseModel):
    """Model for TTS synthesis request"""
    text_to_speech: str = Field(..., min_length=1, max_length=100000)
    voice_id: str = Field(default="Joanna", max_length=50)
    engine: str = Field(default="standard", pattern="^(standard|neural)$")

class SynthesizeResponse(BaseModel):
    """Model for TTS synthesis response with credit-based and tier-based usage tracking"""
    audio_url: str
    speech_marks: List[Dict[str, Any]] = Field(default_factory=list, description="Clean AWS Polly speech marks")
    characters_used: int
    remaining_chars: int  # Legacy field
    duration_seconds: float
    voice_used: Optional[str] = None
    engine_used: Optional[str] = None
    # Credit system fields
    credit_balance: Optional[int] = None
    credits_used: Optional[int] = None
    # Legacy tier-based usage fields (for backward compatibility)
    monthly_usage: Optional[int] = None
    monthly_cap: Optional[int] = None
    usage_percentage: Optional[float] = None
    usage_reset_date: Optional[str] = None
    tier: Optional[str] = None
    is_near_limit: Optional[bool] = None

# User preferences models
class PreferencesUpdate(BaseModel):
    """Model for updating user preferences"""
    engine: Optional[str] = Field(None, pattern="^(standard|neural)$")
    voice_id: Optional[str] = Field(None, max_length=50)

# Stripe models
class StripeCheckoutRequest(BaseModel):
    """Model for Stripe checkout session creation"""
    price_id: str = Field(default="price_1RcGYRQwS4m9kgMV6C1wAZcN")

class CreditCheckoutRequest(BaseModel):
    """Model for credit purchase checkout session creation"""
    credits: int = Field(..., ge=500, le=50000, description="Number of credits to purchase (500 - 50,000)")

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
    highlighting_support: Optional[bool] = None
    speech_marks_compatible: Optional[bool] = None
    recommended_for: Optional[List[str]] = None

class AnalyticsResponse(BaseModel):
    """Model for analytics response"""
    period_days: int
    total_extractions: int
    total_characters: int
    average_extraction_time: float
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

# Analytics / Marketing schemas
class UserCreateWithAttribution(BaseModel):
    """Registration model with UTM / attribution fields for marketing tracking."""
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=6, max_length=128)
    email: EmailStr
    first_name: Optional[str] = Field(default=None, max_length=128)
    last_name: Optional[str] = Field(default=None, max_length=128)
    signup_source: Optional[str] = Field(default=None, max_length=128)
    utm_source: Optional[str] = Field(default=None, max_length=128)
    utm_medium: Optional[str] = Field(default=None, max_length=128)
    utm_campaign: Optional[str] = Field(default=None, max_length=128)
    referred_by: Optional[str] = Field(default=None, description="Username of referring user")

class PlatformStatsResponse(BaseModel):
    """Public marketing endpoint response — powers landing page stats."""
    total_characters_synthesized: int = 0
    total_characters_extracted: int = 0
    total_extractions: int = 0
    total_syntheses: int = 0
    total_users: int = 0
    total_listening_hours: float = 0.0

class UserAnalyticsResponse(BaseModel):
    """Authenticated user's own analytics summary."""
    total_chars_synthesized: int = 0
    total_chars_extracted: int = 0
    total_usage_events: int = 0
    total_lifetime_spend: int = 0
    purchase_count: int = 0
    member_since: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    tier: str = "free"

class AdminAnalyticsOverview(BaseModel):
    """Admin dashboard aggregate analytics."""
    total_users: int = 0
    verified_users: int = 0
    paying_users: int = 0
    total_revenue_cents: int = 0
    avg_revenue_per_user_cents: int = 0
    credit_utilization_pct: float = 0.0
    repeat_purchase_rate_pct: float = 0.0
    signups_last_30_days: int = 0
    purchases_last_30_days: int = 0
    monthly_revenue: List[Dict[str, Any]] = Field(default_factory=list)
    top_utm_sources: List[Dict[str, Any]] = Field(default_factory=list)
    top_extraction_domains: List[Dict[str, Any]] = Field(default_factory=list)