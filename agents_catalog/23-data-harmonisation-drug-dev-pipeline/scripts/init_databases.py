"""
Database initialization script for PostgreSQL and MongoDB.
Creates databases, users, and initial schema structures.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import asyncpg
import psycopg2
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pymongo import MongoClient
from sqlalchemy import create_engine, text

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from config.settings import settings


class DatabaseInitializer:
    """Initialize PostgreSQL and MongoDB databases for the pharmaceutical pipeline."""
    
    def __init__(self):
        self.db_settings = settings.database
        
    async def init_postgresql(self) -> bool:
        """Initialize PostgreSQL database and user."""
        try:
            # Connect to default postgres database to create user and database
            conn = psycopg2.connect(
                host=self.db_settings.postgres_host,
                port=self.db_settings.postgres_port,
                database="postgres",
                user="postgres",  # Assuming postgres superuser exists
                password="postgres"  # Default password, should be changed in production
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()
            
            # Create user if not exists
            cursor.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '{self.db_settings.postgres_user}') THEN
                        CREATE USER {self.db_settings.postgres_user} WITH PASSWORD '{self.db_settings.postgres_password}';
                    END IF;
                END
                $$;
            """)
            
            # Create database if not exists
            cursor.execute(f"""
                SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{self.db_settings.postgres_db}'
            """)
            exists = cursor.fetchone()
            
            if not exists:
                cursor.execute(f"CREATE DATABASE {self.db_settings.postgres_db}")
                logger.info(f"Created PostgreSQL database: {self.db_settings.postgres_db}")
            
            # Grant privileges
            cursor.execute(f"GRANT ALL PRIVILEGES ON DATABASE {self.db_settings.postgres_db} TO {self.db_settings.postgres_user}")
            
            cursor.close()
            conn.close()
            
            # Connect to the new database and create schema
            await self._create_postgresql_schema()
            
            logger.info("PostgreSQL initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL: {e}")
            return False
    
    async def _create_postgresql_schema(self):
        """Create PostgreSQL schema for raw data and metadata."""
        engine = create_engine(self.db_settings.postgres_url)
        
        with engine.connect() as conn:
            # Create raw_data table for storing scraped data
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS raw_data (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    source_company VARCHAR(100) NOT NULL,
                    source_url TEXT NOT NULL,
                    collected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    robots_compliance BOOLEAN NOT NULL,
                    raw_html TEXT,
                    extracted_data JSONB,
                    parsing_method VARCHAR(50),
                    collection_agent VARCHAR(100),
                    validation_status VARCHAR(20) DEFAULT 'pending',
                    content_hash VARCHAR(64),
                    metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # Create indexes for efficient querying
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_raw_data_company ON raw_data(source_company);
                CREATE INDEX IF NOT EXISTS idx_raw_data_collected_at ON raw_data(collected_at);
                CREATE INDEX IF NOT EXISTS idx_raw_data_validation_status ON raw_data(validation_status);
                CREATE INDEX IF NOT EXISTS idx_raw_data_content_hash ON raw_data(content_hash);
            """))
            
            # Create schema_mappings table for data model mappings
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_mappings (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    source_company VARCHAR(100) NOT NULL,
                    source_schema JSONB NOT NULL,
                    unified_schema JSONB NOT NULL,
                    field_mappings JSONB NOT NULL,
                    created_by VARCHAR(100),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # Create data_lineage table for tracking transformations
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS data_lineage (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    source_id UUID REFERENCES raw_data(id),
                    target_collection VARCHAR(100),
                    target_document_id VARCHAR(100),
                    transformation_type VARCHAR(50),
                    transformation_details JSONB,
                    agent_name VARCHAR(100),
                    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # Create quality_reports table for data quality assessments
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS quality_reports (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    data_source VARCHAR(100),
                    assessment_type VARCHAR(50),
                    completeness_score DECIMAL(5,4),
                    consistency_score DECIMAL(5,4),
                    accuracy_score DECIMAL(5,4),
                    overall_score DECIMAL(5,4),
                    issues_found JSONB,
                    recommendations JSONB,
                    assessed_by VARCHAR(100),
                    assessed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            conn.commit()
            logger.info("PostgreSQL schema created successfully")
    
    async def init_mongodb(self) -> bool:
        """Initialize MongoDB database and collections."""
        try:
            # Connect to MongoDB
            client = MongoClient(self.db_settings.mongodb_url)
            db = client[self.db_settings.mongodb_db]
            
            # Create collections with validation schemas
            await self._create_mongodb_collections(db)
            
            client.close()
            logger.info("MongoDB initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize MongoDB: {e}")
            return False
    
    async def _create_mongodb_collections(self, db):
        """Create MongoDB collections for processed data."""
        
        # Unified pipeline data collection
        unified_data_schema = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["compound", "indication", "development", "company"],
                "properties": {
                    "compound": {
                        "bsonType": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"bsonType": "string"},
                            "type": {"bsonType": "string"},
                            "mechanism_of_action": {"bsonType": "string"},
                            "chebi_id": {"bsonType": "string"}
                        }
                    },
                    "indication": {
                        "bsonType": "object",
                        "required": ["primary"],
                        "properties": {
                            "primary": {"bsonType": "string"},
                            "secondary": {"bsonType": "array"},
                            "therapeutic_area": {"bsonType": "string"},
                            "mondo_id": {"bsonType": "string"},
                            "icd10_code": {"bsonType": "string"}
                        }
                    },
                    "development": {
                        "bsonType": "object",
                        "required": ["phase", "status"],
                        "properties": {
                            "phase": {"bsonType": "string"},
                            "status": {"bsonType": "string"},
                            "regulatory_designations": {"bsonType": "array"},
                            "estimated_completion": {"bsonType": "date"}
                        }
                    },
                    "company": {
                        "bsonType": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"bsonType": "string"},
                            "division": {"bsonType": "string"}
                        }
                    }
                }
            }
        }
        
        # Create unified_pipeline_data collection
        if "unified_pipeline_data" not in db.list_collection_names():
            db.create_collection("unified_pipeline_data", validator=unified_data_schema)
            
            # Create indexes for efficient querying
            db.unified_pipeline_data.create_index([("compound.name", 1)])
            db.unified_pipeline_data.create_index([("company.name", 1)])
            db.unified_pipeline_data.create_index([("development.phase", 1)])
            db.unified_pipeline_data.create_index([("indication.therapeutic_area", 1)])
            db.unified_pipeline_data.create_index([("quality_metrics.last_validated", -1)])
        
        # Create ontology_mappings collection
        if "ontology_mappings" not in db.list_collection_names():
            db.create_collection("ontology_mappings")
            db.ontology_mappings.create_index([("term", 1), ("ontology", 1)], unique=True)
        
        # Create agent_logs collection for monitoring
        if "agent_logs" not in db.list_collection_names():
            db.create_collection("agent_logs")
            db.agent_logs.create_index([("timestamp", -1)])
            db.agent_logs.create_index([("agent_name", 1)])
            db.agent_logs.create_index([("level", 1)])
        
        logger.info("MongoDB collections created successfully")
    
    async def test_connections(self) -> bool:
        """Test database connections."""
        try:
            # Test PostgreSQL connection
            engine = create_engine(self.db_settings.postgres_url)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                assert result.fetchone()[0] == 1
            logger.info("PostgreSQL connection test passed")
            
            # Test MongoDB connection
            client = MongoClient(self.db_settings.mongodb_url)
            client.admin.command('ping')
            client.close()
            logger.info("MongoDB connection test passed")
            
            return True
            
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    async def initialize_all(self) -> bool:
        """Initialize both PostgreSQL and MongoDB databases."""
        logger.info("Starting database initialization...")
        
        postgres_success = await self.init_postgresql()
        mongodb_success = await self.init_mongodb()
        
        if postgres_success and mongodb_success:
            connection_test = await self.test_connections()
            if connection_test:
                logger.info("All databases initialized successfully!")
                return True
        
        logger.error("Database initialization failed")
        return False


async def main():
    """Main function to run database initialization."""
    initializer = DatabaseInitializer()
    success = await initializer.initialize_all()
    
    if success:
        logger.info("Database initialization completed successfully")
        sys.exit(0)
    else:
        logger.error("Database initialization failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())