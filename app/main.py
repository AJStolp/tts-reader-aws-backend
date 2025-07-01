"""
Main FastAPI application for TTS Reader API
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import config
from .routes import (
    auth_router, extraction_router, tts_router, 
    user_router, payment_router, admin_router
)
from .services import aws_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Enhanced TTS Reader API with intelligent content extraction...")
    
    # Setup AWS S3 bucket
    await aws_service.setup_bucket()
    
    logger.info("Application startup complete with enhanced extraction capabilities")
    
    yield
    
    # Shutdown
    logger.info("Shutting down TTS Reader API...")

# Create FastAPI app
def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title=config.TITLE,
        description=config.DESCRIPTION,
        version=config.VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(auth_router)
    app.include_router(extraction_router)
    app.include_router(tts_router)
    app.include_router(user_router)
    app.include_router(payment_router)
    app.include_router(admin_router)
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "message": "TTS Reader API - Enhanced Content Extraction for Text-to-Speech",
            "version": config.VERSION,
            "docs": "/docs",
            "health": "/api/health"
        }
    
    return app

# Create the app instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    
    logger.info("=" * 50)
    logger.info("TTS Reader API - Starting Server")
    logger.info("=" * 50)
    logger.info(f"Host: {config.HOST}")
    logger.info(f"Port: {config.PORT}")
    logger.info(f"Workers: {config.WORKERS}")
    logger.info(f"Reload: {config.RELOAD}")
    logger.info("=" * 50)
    
    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
        workers=config.WORKERS if not config.RELOAD else 1,
        log_level="info",
        access_log=True
    )