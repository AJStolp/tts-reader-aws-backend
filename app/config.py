"""
Configuration for TTS Reader API - Enhanced with Enterprise Security - FIXED CORS
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings

class EnterpriseConfig(BaseSettings):
    """Enterprise-grade configuration with security settings - FIXED LOCALHOST SUPPORT"""
    
    # Application Settings
    TITLE: str = "TTS DeepSight API - Enterprise Edition"
    DESCRIPTION: str = "Enterprise-grade Text-to-Speech with advanced content extraction, highlighting, and comprehensive security"
    VERSION: str = "2.3.0-enterprise"
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 5000
    WORKERS: int = 4
    RELOAD: bool = False
    
    # Database Configuration - Supporting both old and new formats
    DATABASE_URL: str = "sqlite:///./database.db"
    DATABASE_CONNECTION_STRING: Optional[str] = None  # Legacy support
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    
    # AWS Configuration
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "tts-neural-reader-data"
    
    # Authentication & Security - Supporting both old and new formats
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_SECRET_KEY: Optional[str] = None  # Legacy support
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # FIXED: CORS Configuration - Allow localhost for development
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001", 
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "https://yourdomain.com",
        "https://app.yourdomain.com",
        "*" if os.getenv("DEVELOPMENT_MODE", "true").lower() == "true" else "https://yourdomain.com"
    ]
    
    # TTS Configuration
    MAX_POLLY_CHARS: int = 3000
    DEFAULT_VOICE_ID: str = "Joanna"
    DEFAULT_ENGINE: str = "neural"

    # Pricing & Tier Configuration
    TIER_FREE_MONTHLY_CAP: int = 0  # Unlimited (web speech API only)
    TIER_PREMIUM_MONTHLY_CAP: int = 2_000_000  # 2M characters
    TIER_PRO_MONTHLY_CAP: int = 10_000_000  # 10M characters

    TIER_PREMIUM_PRICE_MONTHLY: float = 14.00
    TIER_PREMIUM_PRICE_YEARLY: float = 139.99
    TIER_PRO_PRICE_MONTHLY: float = 34.00
    TIER_PRO_PRICE_YEARLY: float = 299.99

    # Stripe Price IDs (set these in .env for production)
    STRIPE_PRICE_ID_PREMIUM_MONTHLY: str = os.getenv("STRIPE_PRICE_ID_PREMIUM_MONTHLY", "")
    STRIPE_PRICE_ID_PREMIUM_YEARLY: str = os.getenv("STRIPE_PRICE_ID_PREMIUM_YEARLY", "")
    STRIPE_PRICE_ID_PRO_MONTHLY: str = os.getenv("STRIPE_PRICE_ID_PRO_MONTHLY", "")
    STRIPE_PRICE_ID_PRO_YEARLY: str = os.getenv("STRIPE_PRICE_ID_PRO_YEARLY", "")

    # Feature Flags
    NEURAL_VOICES_ENABLED: bool = False  # Disabled at launch, enable later for Pro users
    USAGE_WARNING_THRESHOLD: float = 80.0  # Warn at 80% usage
    
    # Stripe Configuration
    STRIPE_API_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    
    # Content Extraction Configuration
    MAX_EXTRACTION_RETRIES: int = 3
    EXTRACTION_TIMEOUT: int = 30
    USER_AGENT: str = "TTS-DeepSight-Bot/2.3.0"
    
    # FIXED: Enterprise Security Configuration - Development-friendly
    ENTERPRISE_SECURITY_ENABLED: bool = True
    SECURITY_AUDIT_LOG_LEVEL: str = "INFO"
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_HOUR: int = 500  # Increased for development
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 30  # Increased for development
    CONTENT_SECURITY_POLICY_ENABLED: bool = True
    AUDIT_LOGGING_ENABLED: bool = True
    ENCRYPTION_ENABLED: bool = True
    
    # FIXED: Development Environment Detection
    DEVELOPMENT_MODE: bool = True  # Set to False in production
    ALLOW_LOCALHOST: bool = True   # Allow localhost in development
    
    # Security Thresholds
    MAX_CONTENT_LENGTH: int = 500000  # 500KB
    MAX_URL_LENGTH: int = 2048
    MAX_USER_AGENT_LENGTH: int = 1000
    SUSPICIOUS_SCORE_THRESHOLD: int = 50
    MAX_EXTRACTION_PROCESSING_TIME: int = 300  # 5 minutes
    MAX_SPEECH_MARKS_SIZE: int = 10000000  # 10MB
    
    # Session Management
    SESSION_TIMEOUT_MINUTES: int = 60
    SESSION_CLEANUP_INTERVAL_MINUTES: int = 15
    MAX_CONCURRENT_SESSIONS_PER_USER: int = 5
    
    # Audit & Compliance
    AUDIT_LOG_RETENTION_DAYS: int = 365
    AUDIT_LOG_MAX_SIZE_MB: int = 1000
    COMPLIANCE_MODE: str = "SOC2"  # SOC2, ISO27001, NIST
    
    # Password Policy
    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_NUMBERS: bool = True
    PASSWORD_REQUIRE_SPECIAL_CHARS: bool = True
    PASSWORD_MAX_AGE_DAYS: int = 90
    
    # API Security
    API_KEY_ENABLED: bool = True
    API_KEY_LENGTH: int = 64
    API_RATE_LIMIT_PER_KEY: int = 1000
    
    # Content Validation
    CONTENT_VALIDATION_ENABLED: bool = True
    XSS_PROTECTION_ENABLED: bool = True
    SQL_INJECTION_PROTECTION_ENABLED: bool = True
    MALWARE_SCANNING_ENABLED: bool = False  # Requires external service
    
    # TLS/SSL Configuration
    TLS_VERSION_MIN: str = "1.2"
    HSTS_MAX_AGE_SECONDS: int = 31536000  # 1 year
    HSTS_INCLUDE_SUBDOMAINS: bool = True
    
    # Monitoring & Alerting
    MONITORING_ENABLED: bool = True
    ALERT_ON_SECURITY_VIOLATIONS: bool = True
    ALERT_ON_PERFORMANCE_ISSUES: bool = True
    PERFORMANCE_THRESHOLD_MS: int = 5000
    
    # Data Protection
    DATA_ENCRYPTION_AT_REST: bool = True
    DATA_ENCRYPTION_IN_TRANSIT: bool = True
    PII_ANONYMIZATION_ENABLED: bool = True
    DATA_RETENTION_DAYS: int = 90
    
    # Backup & Recovery
    BACKUP_ENABLED: bool = True
    BACKUP_INTERVAL_HOURS: int = 24
    BACKUP_RETENTION_DAYS: int = 30
    
    # Feature Flags
    TEXTRACT_EXTRACTION_ENABLED: bool = True
    DOM_EXTRACTION_ENABLED: bool = True
    ADVANCED_HIGHLIGHTING_ENABLED: bool = True
    SPEECH_MARKS_ENABLED: bool = True
    REAL_TIME_PROGRESS_ENABLED: bool = True
    QUALITY_ANALYSIS_ENABLED: bool = True
    CONTENT_CACHING_ENABLED: bool = True
    
    # Performance Settings
    MAX_CONCURRENT_EXTRACTIONS: int = 10
    MAX_CONCURRENT_SYNTHESES: int = 5
    CACHE_TTL_SECONDS: int = 3600  # 1 hour
    MAX_CACHE_SIZE_MB: int = 500
    
    # Error Handling
    DETAILED_ERROR_MESSAGES: bool = False  # Security: Don't expose details in production
    ERROR_TRACKING_ENABLED: bool = True
    EXCEPTION_REPORTING_ENABLED: bool = True
    
    # Development & Debug
    DEBUG_MODE: bool = False
    VERBOSE_LOGGING: bool = False
    PROFILING_ENABLED: bool = False
    
    # Enterprise Integration
    LDAP_ENABLED: bool = False
    LDAP_SERVER: Optional[str] = None
    LDAP_DOMAIN: Optional[str] = None
    
    SAML_ENABLED: bool = False
    SAML_IDP_URL: Optional[str] = None
    SAML_ENTITY_ID: Optional[str] = None
    
    # Webhook Configuration
    WEBHOOK_ENABLED: bool = True
    WEBHOOK_SECRET: str = ""
    WEBHOOK_TIMEOUT_SECONDS: int = 30
    WEBHOOK_RETRY_ATTEMPTS: int = 3
    
    # Redis Configuration (for rate limiting, caching, sessions)
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_SSL: bool = False
    
    # Email Configuration (for alerts, notifications)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True

    # Notification Settings
    SECURITY_ALERT_EMAIL: Optional[str] = None
    ADMIN_ALERT_EMAIL: Optional[str] = None
    PERFORMANCE_ALERT_EMAIL: Optional[str] = None
    
    # API Documentation
    DOCS_ENABLED: bool = True
    REDOC_ENABLED: bool = True
    OPENAPI_URL: str = "/openapi.json"
    
    # Health Check Configuration
    HEALTH_CHECK_ENABLED: bool = True
    HEALTH_CHECK_INTERVAL_SECONDS: int = 30
    HEALTH_CHECK_TIMEOUT_SECONDS: int = 10
    
    # Metrics & Analytics
    METRICS_ENABLED: bool = True
    METRICS_EXPORT_ENABLED: bool = False
    ANALYTICS_ENABLED: bool = True
    USAGE_TRACKING_ENABLED: bool = True
    
    # File Upload Security
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_FILE_TYPES: List[str] = [".txt", ".pdf", ".docx", ".html"]
    VIRUS_SCANNING_ENABLED: bool = False  # Requires external service
    
    # FIXED: IP Security - Development-friendly
    IP_WHITELIST_ENABLED: bool = False
    IP_WHITELIST: List[str] = []
    IP_BLACKLIST_ENABLED: bool = True
    IP_BLACKLIST: List[str] = []
    GEOLOCATION_BLOCKING_ENABLED: bool = False
    BLOCKED_COUNTRIES: List[str] = []
    
    # FIXED: Development IPs that should be allowed
    DEVELOPMENT_IPS: List[str] = [
        "127.0.0.1",
        "::1",
        "localhost"
    ]
    
    # User Security
    MAX_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_DURATION_MINUTES: int = 30
    MFA_ENABLED: bool = False
    MFA_REQUIRED_FOR_ADMIN: bool = True
    
    # Content Security Headers
    CSP_ENABLED: bool = True
    CSP_POLICY: str = "default-src 'self'; script-src 'self'; object-src 'none';"
    FRAME_OPTIONS: str = "DENY"
    CONTENT_TYPE_NOSNIFF: bool = True
    XSS_PROTECTION: str = "1; mode=block"
    
    # Database Security
    DB_ENCRYPTION_ENABLED: bool = True
    DB_CONNECTION_POOL_SIZE: int = 10
    DB_CONNECTION_TIMEOUT: int = 30
    DB_QUERY_TIMEOUT: int = 60
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(lineno)d] %(message)s"
    LOG_TO_FILE: bool = True
    LOG_FILE_PATH: str = "logs/tts_api.log"
    LOG_FILE_MAX_SIZE_MB: int = 100
    LOG_FILE_BACKUP_COUNT: int = 5
    
    # Security Logging
    SECURITY_LOG_ENABLED: bool = True
    SECURITY_LOG_FILE: str = "logs/security_audit.log"
    SECURITY_LOG_LEVEL: str = "INFO"
    FAILED_LOGIN_LOG_ENABLED: bool = True
    
    # Enterprise Features
    MULTI_TENANCY_ENABLED: bool = False
    TENANT_ISOLATION_ENABLED: bool = False
    CUSTOM_BRANDING_ENABLED: bool = False
    WHITE_LABEL_MODE: bool = False
    
    # API Versioning
    API_VERSION: str = "v1"
    API_DEPRECATION_WARNINGS: bool = True
    LEGACY_API_SUPPORT: bool = True
    
    # Internationalization
    DEFAULT_LANGUAGE: str = "en"
    SUPPORTED_LANGUAGES: List[str] = ["en", "es", "fr", "de", "it", "pt"]
    TIMEZONE: str = "UTC"
    
    # Content Processing
    TEXT_PREPROCESSING_ENABLED: bool = True
    HTML_SANITIZATION_ENABLED: bool = True
    MARKDOWN_PROCESSING_ENABLED: bool = True
    LANGUAGE_DETECTION_ENABLED: bool = True
    
    # AWS Services Extended Configuration
    AWS_CLOUDWATCH_ENABLED: bool = False
    AWS_XRAY_ENABLED: bool = False
    AWS_SECRETS_MANAGER_ENABLED: bool = False
    AWS_KMS_ENABLED: bool = False
    
    # Third-party Integrations
    GOOGLE_ANALYTICS_ENABLED: bool = False
    GOOGLE_ANALYTICS_ID: Optional[str] = None
    SENTRY_ENABLED: bool = False
    SENTRY_DSN: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"  # Allow extra fields for backward compatibility
        
        # Security: Validate sensitive fields
        @classmethod
        def parse_env_vars(cls, field_name: str, raw_val: str) -> str:
            """Parse environment variables with security validation"""
            # Sanitize sensitive configuration values
            if field_name in ['SECRET_KEY', 'JWT_SECRET_KEY', 'AWS_SECRET_ACCESS_KEY', 'STRIPE_API_KEY']:
                if len(raw_val) < 16:
                    raise ValueError(f"{field_name} must be at least 16 characters long")
            return raw_val
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Handle legacy configuration mapping
        if self.JWT_SECRET_KEY and not hasattr(self, '_secret_key_set'):
            self.SECRET_KEY = self.JWT_SECRET_KEY
            self._secret_key_set = True
            
        if self.DATABASE_CONNECTION_STRING and not hasattr(self, '_database_url_set'):
            self.DATABASE_URL = self.DATABASE_CONNECTION_STRING
            self._database_url_set = True

class SecurityConfig:
    """Enterprise security configuration constants - FIXED FOR DEVELOPMENT"""
    
    # Security Headers
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; object-src 'none';",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
    }
    
    # Blocked User Agents (Security threats)
    BLOCKED_USER_AGENTS = [
        "sqlmap", "nikto", "nmap", "masscan", "burpsuite", 
        "owasp", "acunetix", "netsparker", "appscan"
    ]
    
    # Suspicious Content Patterns
    SUSPICIOUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'eval\s*\(',
        r'document\.',
        r'window\.',
        r'union\s+select',
        r'drop\s+table',
        r'delete\s+from',
        r'insert\s+into',
        r'--',
        r'/\*.*?\*/',
        r'exec\s*\(',
        r'system\s*\(',
        r'file://',
        r'ftp://',
        r'data:',
    ]
    
    # FIXED: Rate Limiting Configuration - More lenient for development
    RATE_LIMITS = {
        "global": {"requests": 5000, "window": 3600},  # 5000 req/hour global
        "per_user": {"requests": 500, "window": 3600},  # 500 req/hour per user
        "per_ip": {"requests": 1000, "window": 3600},   # 1000 req/hour per IP
        "auth": {"requests": 50, "window": 900},        # 50 auth attempts per 15min
        "extraction": {"requests": 100, "window": 3600}, # 100 extractions per hour
        "synthesis": {"requests": 100, "window": 3600}   # 100 synthesis per hour
    }
    
    # Security Event Types
    SECURITY_EVENT_TYPES = {
        "LOGIN_SUCCESS": "INFO",
        "LOGIN_FAILURE": "MEDIUM",
        "LOGIN_BRUTEFORCE": "HIGH",
        "EXTRACTION_INITIATED": "LOW",
        "EXTRACTION_FAILED": "MEDIUM",
        "CONTENT_SECURITY_VIOLATION": "HIGH",
        "RATE_LIMIT_EXCEEDED": "MEDIUM",
        "SUSPICIOUS_ACTIVITY": "HIGH",
        "DATA_BREACH_ATTEMPT": "CRITICAL",
        "PRIVILEGE_ESCALATION": "CRITICAL",
        "MALWARE_DETECTED": "CRITICAL"
    }

class TierConfig:
    """Tier configuration for pricing and features"""

    TIER_INFO = {
        "free": {
            "name": "Free",
            "price_monthly": 0,
            "price_yearly": 0,
            "monthly_cap": 0,  # Unlimited
            "features": {
                "web_speech_api": True,
                "aws_polly_standard": False,
                "aws_polly_neural": False,
                "speech_marks": False,
                "priority_support": False
            },
            "stripe_price_ids": {}
        },
        "premium": {
            "name": "Premium",
            "price_monthly": 14.00,
            "price_yearly": 139.99,
            "monthly_cap": 2_000_000,
            "features": {
                "web_speech_api": True,
                "aws_polly_standard": True,
                "aws_polly_neural": False,  # Reserved for Pro
                "speech_marks": True,
                "priority_support": False
            },
            "stripe_price_ids": {
                "monthly": os.getenv("STRIPE_PRICE_ID_PREMIUM_MONTHLY", ""),
                "yearly": os.getenv("STRIPE_PRICE_ID_PREMIUM_YEARLY", "")
            },
            "estimated_aws_cost": 8.00,
            "profit_margin": 6.00
        },
        "pro": {
            "name": "Pro",
            "price_monthly": 34.00,
            "price_yearly": 299.99,
            "monthly_cap": 10_000_000,
            "features": {
                "web_speech_api": True,
                "aws_polly_standard": True,
                "aws_polly_neural": True,  # Pro only (when enabled)
                "speech_marks": True,
                "priority_support": True
            },
            "stripe_price_ids": {
                "monthly": os.getenv("STRIPE_PRICE_ID_PRO_MONTHLY", ""),
                "yearly": os.getenv("STRIPE_PRICE_ID_PRO_YEARLY", "")
            },
            "estimated_aws_cost": 40.00,
            "profit_margin": 16.00
        }
    }

    @staticmethod
    def get_tier_info(tier: str) -> dict:
        """Get tier information"""
        return TierConfig.TIER_INFO.get(tier.lower(), TierConfig.TIER_INFO["free"])

    @staticmethod
    def get_monthly_cap(tier: str) -> int:
        """Get monthly character cap for tier"""
        return TierConfig.get_tier_info(tier).get("monthly_cap", 0)

    @staticmethod
    def can_use_engine(tier: str, engine: str) -> bool:
        """Check if tier can use specific engine"""
        tier_info = TierConfig.get_tier_info(tier)
        features = tier_info.get("features", {})

        if engine == "standard":
            return features.get("aws_polly_standard", False)
        elif engine == "neural":
            return features.get("aws_polly_neural", False)

        return False

class CreditConfig:
    """Credit-based pricing configuration"""

    # Credit system constants
    CHARACTERS_PER_CREDIT = 1000  # 1 credit = 1,000 characters

    # Slider range
    CREDIT_MIN = 500  # 500 credits (500k characters) - Perfect for audiobooks
    CREDIT_MAX = 50000  # 50,000 credits (50M characters)

    # Tier thresholds
    LIGHT_CREDIT_THRESHOLD = 500  # 500-1,999 credits = Light tier
    PREMIUM_CREDIT_THRESHOLD = 2000  # 2,000-9,999 credits = Premium tier
    PRO_CREDIT_THRESHOLD = 10000  # 10,000+ credits = Pro tier

    # Pricing rates per credit
    LIGHT_RATE = 0.01  # $0.01 per credit (~$10 per 1,000 credits)
    PREMIUM_RATE = 0.01  # $0.01 per credit (~$10 per 1,000 credits)
    PRO_RATE = 0.01  # $0.01 per credit (~$10 per 1,000 credits)

    # Predefined credit packages (examples for frontend)
    CREDIT_PACKAGES = [
        {
            "credits": 500,
            "tier": "light",
            "price": 5.00,
            "characters": 500_000,
            "rate": 0.01,
            "description": "Audiobook package - Perfect for one book (~8-10 hours)"
        },
        {
            "credits": 1000,
            "tier": "light",
            "price": 10.00,
            "characters": 1_000_000,
            "rate": 0.01,
            "description": "Light usage - 2-3 audiobooks"
        },
        {
            "credits": 2000,
            "tier": "premium",
            "price": 20.00,
            "characters": 2_000_000,
            "rate": 0.01,
            "description": "Regular package - Great for weekly use"
        },
        {
            "credits": 5000,
            "tier": "premium",
            "price": 50.00,
            "characters": 5_000_000,
            "rate": 0.01,
            "description": "Popular package - Heavy monthly usage"
        },
        {
            "credits": 10000,
            "tier": "pro",
            "price": 100.00,
            "characters": 10_000_000,
            "rate": 0.01,
            "description": "Pro package - Best value for power users"
        },
        {
            "credits": 25000,
            "tier": "pro",
            "price": 250.00,
            "characters": 25_000_000,
            "rate": 0.01,
            "description": "Premium package - For heavy usage"
        },
        {
            "credits": 50000,
            "tier": "pro",
            "price": 500.00,
            "characters": 50_000_000,
            "rate": 0.01,
            "description": "Enterprise package - Maximum credits"
        }
    ]

    @staticmethod
    def calculate_price(credits: int) -> float:
        """
        Calculate price for a given number of credits.

        Args:
            credits: Number of credits to purchase

        Returns:
            Price in dollars
        """
        if credits < CreditConfig.CREDIT_MIN:
            raise ValueError(f"Minimum purchase is {CreditConfig.CREDIT_MIN} credits (500k characters)")
        if credits > CreditConfig.CREDIT_MAX:
            raise ValueError(f"Maximum purchase is {CreditConfig.CREDIT_MAX} credits (50M characters)")

        # All tiers now use the same rate of $0.01 per credit
        rate = 0.01

        return round(credits * rate, 2)

    @staticmethod
    def get_tier_for_credits(credits: int) -> str:
        """
        Determine tier based on credit amount.

        Args:
            credits: Number of credits

        Returns:
            Tier name ("light", "premium", or "pro")
        """
        if credits >= CreditConfig.PRO_CREDIT_THRESHOLD:
            return "pro"
        elif credits >= CreditConfig.PREMIUM_CREDIT_THRESHOLD:
            return "premium"
        elif credits >= CreditConfig.LIGHT_CREDIT_THRESHOLD:
            return "light"
        else:
            return "free"

    @staticmethod
    def get_slider_config() -> dict:
        """
        Get slider configuration for frontend.

        Returns:
            Slider configuration dictionary
        """
        return {
            "min": CreditConfig.CREDIT_MIN,
            "max": CreditConfig.CREDIT_MAX,
            "light_threshold": CreditConfig.LIGHT_CREDIT_THRESHOLD,
            "premium_threshold": CreditConfig.PREMIUM_CREDIT_THRESHOLD,
            "pro_threshold": CreditConfig.PRO_CREDIT_THRESHOLD,
            "light_rate": CreditConfig.LIGHT_RATE,
            "premium_rate": CreditConfig.PREMIUM_RATE,
            "pro_rate": CreditConfig.PRO_RATE,
            "characters_per_credit": CreditConfig.CHARACTERS_PER_CREDIT
        }

class PerformanceConfig:
    """Performance and optimization configuration"""

    # Connection Pools
    DB_POOL_SIZE = 20
    DB_MAX_OVERFLOW = 30
    REDIS_POOL_SIZE = 10
    
    # Timeout Settings
    REQUEST_TIMEOUT = 30
    DB_QUERY_TIMEOUT = 60
    EXTRACTION_TIMEOUT = 300
    SYNTHESIS_TIMEOUT = 120
    
    # Caching Configuration
    CACHE_DEFAULT_TTL = 3600  # 1 hour
    CACHE_MAX_SIZE = 1000     # Max items
    CACHE_CLEANUP_INTERVAL = 300  # 5 minutes
    
    # Background Task Configuration
    MAX_BACKGROUND_TASKS = 10
    TASK_TIMEOUT = 600  # 10 minutes
    TASK_RETRY_ATTEMPTS = 3

# Create global configuration instance
config = EnterpriseConfig()

# FIXED: Validation functions with development mode support
def validate_security_config():
    """Validate security configuration on startup - FIXED FOR DEVELOPMENT"""
    errors = []
    
    # Get the effective secret key (handle legacy JWT_SECRET_KEY)
    effective_secret_key = config.SECRET_KEY
    if config.JWT_SECRET_KEY:
        effective_secret_key = config.JWT_SECRET_KEY
    
    # Validate required security settings (relaxed for development)
    if not effective_secret_key or len(effective_secret_key) < 16:  # Reduced from 32 for dev
        errors.append("SECRET_KEY/JWT_SECRET_KEY must be at least 16 characters for development")
    
    if config.ENTERPRISE_SECURITY_ENABLED and not config.AUDIT_LOGGING_ENABLED:
        if not config.DEVELOPMENT_MODE:  # Only enforce in production
            errors.append("Audit logging must be enabled for enterprise security compliance")
    
    if config.TLS_VERSION_MIN not in ["1.2", "1.3"]:
        if not config.DEVELOPMENT_MODE:  # Only enforce in production
            errors.append("TLS version must be 1.2 or higher for enterprise security")
    
    if config.PASSWORD_MIN_LENGTH < 8:  # Reduced from 12 for dev
        errors.append("Password minimum length must be at least 8 characters")
    
    # Validate AWS configuration if Textract is enabled (skip in dev if no credentials)
    if config.TEXTRACT_EXTRACTION_ENABLED and not config.DEVELOPMENT_MODE:
        if not config.AWS_ACCESS_KEY_ID or not config.AWS_SECRET_ACCESS_KEY:
            errors.append("AWS credentials required for Textract extraction")
    
    # Validate database configuration
    effective_db_url = config.DATABASE_URL
    if config.DATABASE_CONNECTION_STRING:
        effective_db_url = config.DATABASE_CONNECTION_STRING
    
    if not effective_db_url:
        errors.append("Database configuration required (DATABASE_URL or DATABASE_CONNECTION_STRING)")
    
    if errors:
        raise ValueError(f"Security configuration validation failed: {'; '.join(errors)}")
    
    # Log successful validation with legacy field mapping
    import logging
    logger = logging.getLogger(__name__)
    logger.info("✅ Enterprise security configuration validated successfully")
    if config.DEVELOPMENT_MODE:
        logger.info("🛠️ Running in DEVELOPMENT MODE - security relaxed for localhost")
    if config.JWT_SECRET_KEY:
        logger.info("📋 Legacy JWT_SECRET_KEY mapped to SECRET_KEY")
    if config.DATABASE_CONNECTION_STRING:
        logger.info("📋 Legacy DATABASE_CONNECTION_STRING mapped to DATABASE_URL")

def get_environment_info():
    """Get current environment information"""
    return {
        "environment": os.getenv("ENVIRONMENT", "development"),
        "debug_mode": config.DEBUG_MODE,
        "development_mode": config.DEVELOPMENT_MODE,
        "allow_localhost": config.ALLOW_LOCALHOST,
        "enterprise_security": config.ENTERPRISE_SECURITY_ENABLED,
        "version": config.VERSION,
        "features": {
            "textract": config.TEXTRACT_EXTRACTION_ENABLED,
            "highlighting": config.ADVANCED_HIGHLIGHTING_ENABLED,
            "speech_marks": config.SPEECH_MARKS_ENABLED,
            "audit_logging": config.AUDIT_LOGGING_ENABLED,
            "rate_limiting": config.RATE_LIMIT_ENABLED
        }
    }

# Export commonly used configurations
__all__ = [
    "config",
    "SecurityConfig",
    "TierConfig",
    "PerformanceConfig",
    "validate_security_config",
    "get_environment_info"
]