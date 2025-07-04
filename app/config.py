"""
Configuration and settings for TTS Reader API
"""
import os
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AppConfig:
    """Application configuration settings"""
    
    # Basic app info
    TITLE = "TTS Reader API"
    DESCRIPTION = "Enhanced API for text extraction and synthesis with intelligent content processing"
    VERSION = "2.2.0"
    
    # Security settings
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    
    # AWS settings
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "tts-neural-reader-data")
    
    # Database
    DATABASE_CONNECTION_STRING = os.environ.get("DATABASE_CONNECTION_STRING")
    
    # Stripe
    STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
    
    # CORS settings - FIXED for Chrome extension
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:5000",
        "http://127.0.0.1:3000", 
        "http://127.0.0.1:5000",
        "https://localhost:3000",
        "chrome-extension://*",  # Allow all Chrome extensions
        "*"  # Allow all origins for development (restrict in production)
    ]
    
    # TTS settings
    MAX_POLLY_CHARS = 3000  # Conservative limit for Polly
    
    # Server settings
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", "5000"))
    WORKERS = int(os.environ.get("WORKERS", "1"))
    RELOAD = os.environ.get("RELOAD", "false").lower() == "true"
    
    def __post_init__(self):
        # Add additional origins from environment
        env_origins = os.environ.get("ALLOWED_ORIGINS", "")
        if env_origins:
            self.ALLOWED_ORIGINS.extend(env_origins.split(","))
    
    @classmethod
    def validate_required_env_vars(cls) -> List[str]:
        """Validate that all required environment variables are set"""
        required_vars = [
            "JWT_SECRET_KEY",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_REGION",
            "DATABASE_CONNECTION_STRING"
        ]
        
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        return missing_vars

# Global configuration instance
config = AppConfig()

# Validate environment on import
missing_vars = config.validate_required_env_vars()
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")