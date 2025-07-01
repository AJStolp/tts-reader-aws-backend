"""
TTS Reader API Application Package

This package contains a modern, enterprise-grade FastAPI application 
specifically designed for text-to-speech content extraction and synthesis.

Key Features:
- Intelligent content extraction optimized for TTS
- Multiple extraction strategies with automatic fallbacks
- AWS Polly integration for high-quality speech synthesis
- User management with JWT authentication
- Stripe payment integration
- Real-time progress tracking
- Comprehensive analytics and monitoring
- Clean, modular architecture
"""

from .main import app
from .config import config

__version__ = "2.2.0"
__title__ = "TTS Reader API"
__description__ = "Enhanced API for text extraction and synthesis with intelligent content processing"

# Export main app instance
__all__ = ["app", "config"]