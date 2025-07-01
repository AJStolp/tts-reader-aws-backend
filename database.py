import os
import logging
from typing import Generator
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_CONNECTION_STRING = os.environ.get("DATABASE_CONNECTION_STRING")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")

if not DATABASE_CONNECTION_STRING:
    raise ValueError(
        "DATABASE_CONNECTION_STRING environment variable is required. "
        "Please set it to your Supabase PostgreSQL connection string."
    )

# Validate Supabase connection string format
if not DATABASE_CONNECTION_STRING.startswith("postgresql://"):
    raise ValueError(
        "DATABASE_CONNECTION_STRING must be a valid PostgreSQL connection string "
        "starting with 'postgresql://'"
    )

# Engine configuration optimized for Supabase
engine_kwargs = {
    "pool_size": 10,
    "max_overflow": 20,
    "pool_pre_ping": True,
    "pool_recycle": 3600,  # Recycle connections every hour
    "echo": ENVIRONMENT == "development",  # SQL logging in development
}

# Create engine
try:
    engine = create_engine(DATABASE_CONNECTION_STRING, **engine_kwargs)
    logger.info("Successfully configured Supabase database engine")
except Exception as e:
    logger.error(f"Failed to create database engine: {str(e)}")
    raise

# Session configuration
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

# Database metadata for migrations
metadata = MetaData()

class DatabaseManager:
    """Database manager for handling connections and transactions"""
    
    @staticmethod
    def get_db() -> Generator[Session, None, None]:
        """
        Database dependency for FastAPI endpoints.
        Provides a database session and ensures proper cleanup.
        """
        db = SessionLocal()
        try:
            yield db
        except Exception as e:
            logger.error(f"Database session error: {str(e)}")
            db.rollback()
            raise
        finally:
            db.close()
    
    @staticmethod
    def create_tables():
        """Create all tables defined in models"""
        try:
            # Import models to register them with Base
            from models import User
            
            # For production, we'll use Alembic migrations instead of create_all
            # Base.metadata.create_all(bind=engine)
            logger.info("Database tables managed by Alembic migrations")
        except Exception as e:
            logger.error(f"Failed to import models: {str(e)}")
            raise
    
    @staticmethod
    def test_connection() -> bool:
        """Test database connectivity"""
        try:
            with engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                result.fetchone()  # Actually fetch the result
            logger.info("Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {str(e)}")
            return False
    
    @staticmethod
    def get_connection_info() -> dict:
        """Get database connection information (without sensitive data)"""
        url = engine.url
        return {
            "database": url.database,
            "host": url.host,
            "port": url.port,
            "driver": url.drivername,
            "pool_size": engine.pool.size(),
            "checked_out": engine.pool.checkedout(),
        }

# Database health check
async def health_check() -> dict:
    """Health check for database connectivity"""
    try:
        db_manager = DatabaseManager()
        is_healthy = db_manager.test_connection()
        
        return {
            "database": "healthy" if is_healthy else "unhealthy",
            "connection_info": db_manager.get_connection_info() if is_healthy else None,
            "engine_pool": {
                "size": engine.pool.size(),
                "checked_out": engine.pool.checkedout(),
                "overflow": engine.pool.overflow(),
            }
        }
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return {
            "database": "unhealthy",
            "error": str(e)
        }

# Utility functions for the database dependency
def get_db():
    """FastAPI dependency for database sessions"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()