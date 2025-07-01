import os
import sys
import asyncio
import logging
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_dependencies():
    """Check if all required dependencies are available"""
    logger.info("Checking dependencies...")
    
    # Check environment variables
    required_env_vars = [
        "JWT_SECRET_KEY",
        "AWS_ACCESS_KEY_ID", 
        "AWS_SECRET_ACCESS_KEY",
        "AWS_REGION",
        "DATABASE_CONNECTION_STRING"  # Added Supabase connection string
    ]
    
    missing_vars = []
    for var in required_env_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file or environment configuration")
        return False
    
    # Check Playwright browsers
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            await browser.close()
        logger.info("✓ Playwright browsers are available")
    except Exception as e:
        logger.error(f"✗ Playwright browser check failed: {e}")
        logger.error("Run 'playwright install' to install browsers")
        return False
    
    # Check AWS credentials
    try:
        import boto3
        session = boto3.Session(
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_REGION")
        )
        
        # Test S3 access
        s3 = session.client("s3")
        s3.list_buckets()
        logger.info("✓ AWS S3 credentials are valid")
        
        # Test Polly access
        polly = session.client("polly")
        polly.describe_voices(LanguageCode="en-US")
        logger.info("✓ AWS Polly access is working")
        
        # Test Textract access (optional)
        try:
            textract = session.client("textract")
            # This will fail with InvalidJobIdException, which is expected
            await asyncio.to_thread(textract.get_document_analysis, JobId="test")
        except Exception as e:
            if "InvalidJobIdException" in str(e):
                logger.info("✓ AWS Textract access is working")
            else:
                logger.warning(f"⚠ AWS Textract access issue: {e}")
                logger.warning("Textract features may be limited")
        
    except Exception as e:
        logger.error(f"✗ AWS credentials check failed: {e}")
        return False
    
    logger.info("All dependency checks passed!")
    return True

async def initialize_database():
    """Initialize Supabase database connection"""
    logger.info("Initializing database...")
    
    try:
        # Import our Supabase database manager
        from database import DatabaseManager
        
        # Test database connection
        db_manager = DatabaseManager()
        if not db_manager.test_connection():
            logger.error("✗ Failed to connect to Supabase database")
            return False
        
        logger.info("✓ Database tables created/verified")
        return True
        
    except Exception as e:
        logger.error(f"✗ Database initialization failed: {e}")
        logger.error(f"Full error: {str(e)}")
        return False

def main():
    """Main startup function"""
    logger.info("=" * 50)
    logger.info("TTS Reader API - Starting Up")
    logger.info("=" * 50)
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Run async checks
    async def startup_checks():
        deps_ok = await check_dependencies()
        if not deps_ok:
            logger.error("Dependency checks failed. Exiting.")
            sys.exit(1)
        
        db_ok = await initialize_database()
        if not db_ok:
            logger.error("Database initialization failed. Exiting.")
            sys.exit(1)
        
        logger.info("✓ All startup checks passed!")
        logger.info("Starting FastAPI server...")
    
    # Run startup checks
    asyncio.run(startup_checks())
    
    # Start the server
    import uvicorn
    
    # Get configuration from environment
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    workers = int(os.environ.get("WORKERS", "1"))
    reload = os.environ.get("RELOAD", "false").lower() == "true"
    
    logger.info(f"Server configuration:")
    logger.info(f"  Host: {host}")
    logger.info(f"  Port: {port}")
    logger.info(f"  Workers: {workers}")
    logger.info(f"  Reload: {reload}")
    logger.info("=" * 50)
    
    try:
        # Import here to test if the app module loads correctly
        import app
        logger.info("✓ App module imports successfully")
        
        uvicorn.run(
            app.app,  # Direct reference to the app object
            host=host,
            port=port,
            workers=workers,
            reload=reload,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()