"""
TTS-optimized content extraction package

This package provides intelligent content extraction specifically optimized for 
text-to-speech applications, with multiple extraction strategies and fallbacks.
"""
import os
import logging
import asyncio
from typing import Tuple, Dict, Any
import boto3
from botocore.exceptions import ClientError

from .config import ExtractionMethod, ContentType, DEFAULT_CONFIG
from .models import ExtractionResult
from .manager import ContentExtractorManager
from .utils import URLValidator

# Configure logging
logger = logging.getLogger(__name__)

# Initialize AWS Textract client
_textract_client = None

try:
    session = boto3.Session(
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_REGION", "us-east-1")
    )
    
    textract = session.client("textract")
    
    # Test Textract connectivity
    textract.get_document_analysis(JobId="test-connectivity")
    _textract_client = textract
    logger.info("AWS Textract client initialized successfully for TTS extraction")
    
except ClientError as e:
    if "InvalidJobIdException" not in str(e):
        logger.warning(f"Textract client issue: {str(e)}")
    else:
        _textract_client = textract
        logger.info("AWS Textract client initialized successfully for TTS extraction")
except Exception as e:
    logger.error(f"Failed to initialize AWS Textract client: {str(e)}")
    logger.info("TTS extraction will use DOM-only methods")

# Global extraction manager instance
_global_manager = None

def get_extraction_manager() -> ContentExtractorManager:
    """Get or create the global extraction manager instance"""
    global _global_manager
    if _global_manager is None:
        _global_manager = ContentExtractorManager(_textract_client, DEFAULT_CONFIG)
    return _global_manager

# Main extraction functions (backwards compatibility)
async def extract_content(url: str) -> Tuple[str, str]:
    """
    Main extraction function optimized for TTS content
    
    Args:
        url (str): The webpage URL to process
        
    Returns:
        Tuple[str, str]: (extracted_text, extraction_method)
    """
    manager = get_extraction_manager()
    return await manager.extract_content(url)

async def is_valid_url(url: str) -> bool:
    """Validate URL format"""
    return await URLValidator.is_valid_url(url)

async def health_check() -> Dict[str, Any]:
    """
    Comprehensive health check for the TTS extraction service
    
    Returns:
        Dict containing health status information
    """
    from datetime import datetime
    from playwright.async_api import async_playwright
    
    status = {
        "textract_available": _textract_client is not None,
        "playwright_available": False,
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "capabilities": [],
        "service": "TTS Content Extractor",
        "version": "2.0.0"
    }
    
    # Test Playwright
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            await browser.close()
        status["playwright_available"] = True
        status["capabilities"].extend(["dom_extraction", "reader_mode", "heuristic_analysis"])
        logger.info("✓ Playwright health check passed")
    except Exception as e:
        status["playwright_available"] = False
        status["playwright_error"] = str(e)
        status["status"] = "degraded"
        logger.error(f"✗ Playwright health check failed: {e}")
    
    # Test Textract (if available)
    if _textract_client:
        try:
            await asyncio.to_thread(_textract_client.describe_document_analysis, JobId="health-check")
        except ClientError as e:
            if "InvalidJobIdException" in str(e):
                status["capabilities"].append("textract_extraction")
                logger.info("✓ Textract health check passed")
            else:
                status["textract_available"] = False
                status["textract_error"] = str(e)
                status["status"] = "degraded"
                logger.error(f"✗ Textract health check failed: {e}")