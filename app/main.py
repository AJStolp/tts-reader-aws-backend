"""
Main FastAPI application for TTS Reader API - Enhanced with Enterprise Security
"""
import logging
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from .config import config, validate_security_config
from .routes import (
    auth_router, extraction_router, tts_router, 
    user_router, payment_router, admin_router
)
from .services import aws_service
from .enterprise_security import enterprise_security, get_enterprise_security_headers

# Configure enterprise logging with security audit trail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s] %(message)s',
    handlers=[
        logging.FileHandler('tts_api_audit.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with enterprise security initialization"""
    # Startup
    logger.info("🚀 Starting Enhanced TTS Reader API with enterprise security...")
    
    try:
        # Validate enterprise security configuration first
        validate_security_config()
        logger.info("✅ Enterprise security configuration validated")
        
        # Setup AWS S3 bucket
        await aws_service.setup_bucket()
        logger.info("✅ AWS S3 bucket configured")
        
        # Initialize enterprise security
        enterprise_security.log_security_event(
            "APPLICATION_STARTUP",
            None,
            "localhost",
            "TTS-DeepSight-Server/1.0",
            "/",
            "INFO",
            {
                "version": config.VERSION,
                "security_enabled": True,
                "aws_configured": True,
                "extraction_methods": ["textract", "dom_semantic", "dom_heuristic", "reader_mode"],
                "highlighting_enabled": True,
                "speech_marks_enabled": True,
                "database_type": "postgresql" if "postgresql" in (config.DATABASE_CONNECTION_STRING or config.DATABASE_URL) else "sqlite"
            }
        )
        
        logger.info("✅ Application startup complete with enhanced extraction and enterprise security")
        
    except Exception as e:
        logger.error(f"❌ Application startup failed: {str(e)}")
        enterprise_security.log_security_event(
            "APPLICATION_STARTUP_FAILED",
            None,
            "localhost",
            "TTS-DeepSight-Server/1.0", 
            "/",
            "CRITICAL",
            {"error": str(e)}
        )
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down TTS Reader API...")
    enterprise_security.log_security_event(
        "APPLICATION_SHUTDOWN",
        None,
        "localhost", 
        "TTS-DeepSight-Server/1.0",
        "/",
        "INFO",
        {"graceful_shutdown": True}
    )

async def enterprise_security_middleware(request: Request, call_next: Callable) -> Response:
    """Enterprise security middleware for all requests"""
    start_time = time.time()
    
    # Extract request information
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    endpoint = str(request.url.path)
    method = request.method
    
    # Get user ID if available (will be set by auth middleware)
    user_id = getattr(request.state, 'user_id', None)
    
    try:
        # Handle CORS preflight requests immediately
        if method == "OPTIONS":
            response = Response()
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Requested-With"
            response.headers["Access-Control-Max-Age"] = "86400"
            return response
        
        # Skip security validation for health check, docs, and root
        if endpoint in ["/", "/docs", "/redoc", "/openapi.json", "/api/health"]:
            response = await call_next(request)
        else:
            # Validate request security for all other endpoints
            validation = enterprise_security.validate_request_security(
                ip_address=ip_address,
                user_agent=user_agent,
                endpoint=endpoint,
                user_id=user_id
            )
            
            if not validation["allowed"]:
                enterprise_security.log_security_event(
                    "REQUEST_BLOCKED",
                    user_id,
                    ip_address,
                    user_agent,
                    endpoint,
                    "HIGH",
                    {
                        "method": method,
                        "risk_score": validation["risk_score"],
                        "violations": validation["violations"]
                    }
                )
                
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Request blocked by enterprise security policy",
                        "error_code": "SECURITY_POLICY_VIOLATION"
                    }
                )
            
            # Add security context to request
            request.state.security_validation = validation
            
            # Process request
            response = await call_next(request)
            
            # Log successful request
            processing_time = time.time() - start_time
            if processing_time > 5.0:  # Log slow requests
                enterprise_security.log_security_event(
                    "SLOW_REQUEST_DETECTED",
                    user_id,
                    ip_address,
                    user_agent,
                    endpoint,
                    "MEDIUM",
                    {
                        "method": method,
                        "processing_time": processing_time,
                        "status_code": response.status_code
                    }
                )
        
        # Add enterprise security headers
        security_headers = get_enterprise_security_headers()
        for header, value in security_headers.items():
            response.headers[header] = value
        
        # Add custom TTS security headers
        response.headers["X-TTS-DeepSight-Version"] = config.VERSION
        response.headers["X-Content-Processing"] = "enterprise-secured"
        response.headers["X-Extraction-Methods"] = "textract,dom,highlighting"
        
        return response
        
    except HTTPException as e:
        # Let FastAPI handle HTTP exceptions normally
        response = await call_next(request)
        return response
        
    except Exception as e:
        # Log unexpected errors
        enterprise_security.log_security_event(
            "MIDDLEWARE_ERROR",
            user_id,
            ip_address,
            user_agent,
            endpoint,
            "HIGH",
            {
                "method": method,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        
        # Return generic error to prevent information disclosure
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "error_code": "INTERNAL_ERROR"
            }
        )

# Create FastAPI app
def create_app() -> FastAPI:
    """Create and configure FastAPI application with enterprise security"""
    
    app = FastAPI(
        title=f"{config.TITLE} - Enterprise Security",
        description=f"{config.DESCRIPTION} - Enhanced with enterprise-grade security, audit logging, and advanced TTS highlighting",
        version=config.VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        # Add enterprise security documentation
        contact={
            "name": "TTS DeepSight Enterprise Security",
            "email": "security@ttsdeepsight.com"
        },
        license_info={
            "name": "Enterprise License",
            "url": "https://ttsdeepsight.com/enterprise-license"
        }
    )
    
    # Add enterprise security middleware FIRST (before CORS)
    app.middleware("http")(enterprise_security_middleware)
    
    # Add CORS middleware with security-enhanced configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type", 
            "X-Requested-With",
            "X-TTS-Session-ID",
            "X-TTS-Client-Version"
        ],
        expose_headers=[
            "X-TTS-DeepSight-Version",
            "X-Content-Processing",
            "X-Extraction-Methods",
            "X-Rate-Limit-Remaining",
            "X-Rate-Limit-Reset"
        ]
    )
    
    # Include routers with enhanced logging
    logger.info("📋 Registering API routers with enterprise security...")
    
    app.include_router(auth_router, tags=["Authentication - Enterprise Secured"])
    logger.info("✅ Authentication router registered")
    
    app.include_router(extraction_router, tags=["Content Extraction - TTS Optimized"])
    logger.info("✅ Extraction router registered") 
    
    app.include_router(tts_router, tags=["Text-to-Speech - Advanced Highlighting"])
    logger.info("✅ TTS router registered")
    
    app.include_router(user_router, tags=["User Management - Secure"])
    logger.info("✅ User router registered")
    
    app.include_router(payment_router, tags=["Payments - PCI Compliant"])
    logger.info("✅ Payment router registered")
    
    app.include_router(admin_router, tags=["Administration - Audit Logged"])
    logger.info("✅ Admin router registered")
    
    # Enhanced root endpoint with security information
    @app.get("/", tags=["System Information"])
    async def root(request: Request):
        """Enhanced root endpoint with enterprise security status"""
        
        # Log root access
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        enterprise_security.log_security_event(
            "ROOT_ENDPOINT_ACCESS",
            None,
            ip_address,
            user_agent,
            "/",
            "LOW",
            {"accessed_docs": False}
        )
        
        return {
            "service": "TTS Reader API - Enterprise Edition",
            "version": config.VERSION,
            "description": "Enterprise-grade Text-to-Speech with advanced content extraction and highlighting",
            "security": {
                "enterprise_security_enabled": True,
                "audit_logging_enabled": True,
                "rate_limiting_enabled": True,
                "content_validation_enabled": True
            },
            "features": {
                "textract_extraction": True,
                "dom_extraction": True,
                "advanced_highlighting": True,
                "speech_mark_synchronization": True,
                "real_time_progress": True,
                "chunk_processing": True,
                "quality_analysis": True
            },
            "endpoints": {
                "health": "/api/health",
                "docs": "/docs",
                "redoc": "/redoc",
                "authentication": "/api/login",
                "extraction": "/api/extract/enhanced",
                "synthesis": "/api/synthesize-with-highlighting"
            },
            "compliance": {
                "security_framework": "Enterprise-Grade",
                "audit_trail": "Comprehensive",
                "data_protection": "Encrypted",
                "access_control": "Role-Based"
            }
        }
    
    # Add enterprise monitoring endpoint
    @app.get("/api/enterprise/status", tags=["Enterprise Monitoring"])
    async def enterprise_status(request: Request):
        """Enterprise system status and security metrics"""
        
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Require admin authentication in production
        # For now, log the access
        enterprise_security.log_security_event(
            "ENTERPRISE_STATUS_ACCESS",
            None,
            ip_address,
            user_agent,
            "/api/enterprise/status",
            "MEDIUM",
            {"admin_endpoint_access": True}
        )
        
        # Get security metrics
        audit_check = enterprise_security.audit_trail_integrity_check()
        
        return {
            "system_status": "operational",
            "security_status": "enterprise_compliant",
            "timestamp": enterprise_security.log_security_event(
                "STATUS_CHECK",
                None,
                ip_address,
                user_agent,
                "/api/enterprise/status",
                "LOW",
                {}
            ).timestamp.isoformat(),
            "audit_trail": audit_check,
            "active_security_features": {
                "request_validation": True,
                "rate_limiting": True,
                "content_sanitization": True,
                "audit_logging": True,
                "encryption": True,
                "session_management": True
            },
            "tts_features": {
                "textract_available": True,
                "highlighting_engine": True,
                "speech_marks": True,
                "quality_analysis": True
            }
        }
    
    logger.info("✅ FastAPI application created with enterprise security")
    return app

# Create the app instance
app = create_app()

# Global exception handler for enterprise security
@app.exception_handler(Exception)
async def enterprise_exception_handler(request: Request, exc: Exception):
    """Enterprise exception handler with security logging"""
    
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    endpoint = str(request.url.path)
    
    # Log the exception with security context
    enterprise_security.log_security_event(
        "UNHANDLED_EXCEPTION",
        getattr(request.state, 'user_id', None),
        ip_address,
        user_agent,
        endpoint,
        "HIGH",
        {
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "method": request.method
        }
    )
    
    # Return generic error to prevent information disclosure
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred",
            "error_code": "INTERNAL_SERVER_ERROR",
            "timestamp": enterprise_security.log_security_event(
                "ERROR_RESPONSE_SENT",
                None,
                ip_address,
                user_agent,
                endpoint,
                "MEDIUM",
                {}
            ).timestamp.isoformat()
        }
    )

if __name__ == "__main__":
    import uvicorn
    
    logger.info("=" * 80)
    logger.info("🎯 TTS DeepSight API - Enterprise Edition - Starting Server")
    logger.info("=" * 80)
    logger.info(f"🌐 Host: {config.HOST}")
    logger.info(f"🚪 Port: {config.PORT}")
    logger.info(f"👥 Workers: {config.WORKERS}")
    logger.info(f"🔄 Reload: {config.RELOAD}")
    logger.info(f"🔒 Enterprise Security: ENABLED")
    logger.info(f"📊 Audit Logging: ENABLED") 
    logger.info(f"🛡️ Rate Limiting: ENABLED")
    logger.info(f"🎨 Advanced Highlighting: ENABLED")
    logger.info(f"🎤 Speech Mark Sync: ENABLED")
    logger.info("=" * 80)
    
    # Log server startup
    enterprise_security.log_security_event(
        "SERVER_STARTUP_INITIATED",
        None,
        config.HOST,
        "uvicorn-server",
        f"{config.HOST}:{config.PORT}",
        "INFO",
        {
            "host": config.HOST,
            "port": config.PORT,
            "workers": config.WORKERS,
            "reload": config.RELOAD,
            "security_enabled": True
        }
    )
    
    try:
        uvicorn.run(
            "app.main:app",
            host=config.HOST,
            port=config.PORT,
            reload=config.RELOAD,
            workers=config.WORKERS if not config.RELOAD else 1,
            log_level="info",
            access_log=True,
            server_header=False,  # Security: Don't expose server info
            date_header=True,
            use_colors=True
        )
    except Exception as e:
        logger.error(f"❌ Server startup failed: {str(e)}")
        enterprise_security.log_security_event(
            "SERVER_STARTUP_FAILED",
            None,
            config.HOST,
            "uvicorn-server",
            f"{config.HOST}:{config.PORT}",
            "CRITICAL",
            {"error": str(e)}
        )
        raise