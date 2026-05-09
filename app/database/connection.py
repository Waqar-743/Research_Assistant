"""
MongoDB Database Connection and Management
Uses Motor for async MongoDB operations with Beanie ODM.
Includes GridFS support for document file storage.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket
from beanie import init_beanie
from typing import Optional

from app.config import settings
from app.utils.logging import logger


class MongoDB:
    """MongoDB connection manager with GridFS support."""
    
    client: Optional[AsyncIOMotorClient] = None
    database: Optional[AsyncIOMotorDatabase] = None
    fs: Optional[AsyncIOMotorGridFSBucket] = None  # GridFS for file storage


db = MongoDB()


async def connect_to_mongo():
    """
    Establish connection to MongoDB.
    Initializes Beanie ODM with document models.
    """
    try:
        logger.info(f"Connecting to MongoDB at {settings.mongodb_url[:30]}...")
        
        db.client = AsyncIOMotorClient(
            settings.mongodb_url,
            maxPoolSize=50,
            minPoolSize=10,
            serverSelectionTimeoutMS=5000
        )
        
        db.database = db.client[settings.mongodb_database]
        
        # Initialize Beanie with document models
        from app.database.schemas import (
            ResearchSession,
            Source,
            Finding,
            Report,
            AgentLog,
            User
        )
        from app.database.document_schemas import (
            UploadedDocument,
            DocumentCitation,
            DocumentComparison,
            UserSettings,
            ConversationHistory
        )
        
        await init_beanie(
            database=db.database,
            document_models=[
                ResearchSession,
                Source,
                Finding,
                Report,
                AgentLog,
                User,
                # Document analysis models
                UploadedDocument,
                DocumentCitation,
                DocumentComparison,
                UserSettings,
                ConversationHistory
            ]
        )
        
        # Initialize GridFS for document file storage
        db.fs = AsyncIOMotorGridFSBucket(db.database, bucket_name="document_files")
        logger.info("GridFS initialized for document storage")
        
        # Verify connection
        await db.client.admin.command('ping')
        logger.info(f"Connected to MongoDB database: {settings.mongodb_database}")
        
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}", exc_info=True)
        logger.warning("Running in degraded mode — all database operations will return 503")
        # Reset everything so db.database is None → callers get a clean 503
        db.client = None
        db.database = None
        db.fs = None


async def close_mongo_connection():
    """Close MongoDB connection."""
    if db.client:
        db.client.close()
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """Get database instance for dependency injection."""
    if db.database is None:
        raise RuntimeError("Database not initialized. Call connect_to_mongo() first.")
    return db.database


async def get_db():
    """Dependency for FastAPI routes."""
    return get_database()


def get_gridfs() -> AsyncIOMotorGridFSBucket:
    """Get GridFS bucket for file operations."""
    if db.fs is None:
        raise RuntimeError("GridFS not initialized. Call connect_to_mongo() first.")
    return db.fs


async def check_database_connection() -> bool:
    """
    Check if database connection is healthy.
    Returns True if connection is working, False otherwise.
    """
    if db.client is None:
        return False
    try:
        await db.client.admin.command('ping')
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
