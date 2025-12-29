"""Storage manager for pharmaceutical pipeline data."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from ..models.pipeline_data import RawPipelineData, StorageResult
from ..models.harmonization import (
    DeduplicatedData,
    EnrichedData,
    SchemaAnalysis,
    UnifiedDataModel,
)

logger = logging.getLogger(__name__)


class StorageManager:
    """Manages data persistence in PostgreSQL database."""
    
    def __init__(
        self,
        connection_string: str,
        schema_name: str = "pharma_pipeline"
    ):
        """Initialize the storage manager.
        
        Args:
            connection_string: PostgreSQL connection string
            schema_name: Database schema name
        """
        self.connection_string = connection_string
        self.schema_name = schema_name
        self.engine = create_engine(connection_string)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Initialize database schema
        self._initialize_schema()
        
        logger.info(f"Initialized StorageManager with schema: {schema_name}")
    
    def _initialize_schema(self):
        """Initialize database schema and tables."""
        try:
            with self.engine.connect() as conn:
                # Create schema if it doesn't exist
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {self.schema_name}"))
                
                # Create raw_pipeline_data table
                create_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {self.schema_name}.raw_pipeline_data (
                    id UUID PRIMARY KEY,
                    company VARCHAR(255) NOT NULL,
                    source_url TEXT NOT NULL,
                    collected_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    robots_compliance BOOLEAN NOT NULL,
                    collection_agent VARCHAR(255) NOT NULL,
                    raw_html TEXT NOT NULL,
                    extracted_data JSONB NOT NULL,
                    parsing_method VARCHAR(255) NOT NULL,
                    content_hash VARCHAR(64) NOT NULL,
                    validation_status JSONB,
                    metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                """
                conn.execute(text(create_table_sql))
                
                # Create indexes for better query performance
                indexes = [
                    f"CREATE INDEX IF NOT EXISTS idx_raw_pipeline_company ON {self.schema_name}.raw_pipeline_data(company)",
                    f"CREATE INDEX IF NOT EXISTS idx_raw_pipeline_collected_at ON {self.schema_name}.raw_pipeline_data(collected_at)",
                    f"CREATE INDEX IF NOT EXISTS idx_raw_pipeline_content_hash ON {self.schema_name}.raw_pipeline_data(content_hash)",
                    f"CREATE INDEX IF NOT EXISTS idx_raw_pipeline_extraction ON {self.schema_name}.raw_pipeline_data USING GIN(extracted_data)",
                ]
                
                for index_sql in indexes:
                    conn.execute(text(index_sql))
                
                # Create data lineage table
                lineage_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {self.schema_name}.data_lineage (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    source_record_id UUID NOT NULL,
                    operation_type VARCHAR(50) NOT NULL,
                    operation_details JSONB,
                    performed_by VARCHAR(255) NOT NULL,
                    performed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    FOREIGN KEY (source_record_id) REFERENCES {self.schema_name}.raw_pipeline_data(id)
                );
                """
                conn.execute(text(lineage_table_sql))
                
                # Create schema analysis table
                schema_analysis_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {self.schema_name}.schema_analysis (
                    id UUID PRIMARY KEY,
                    total_sources INTEGER NOT NULL,
                    schemas JSONB NOT NULL,
                    common_fields JSONB NOT NULL,
                    analysis_metadata JSONB,
                    analyzed_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                """
                conn.execute(text(schema_analysis_table_sql))
                
                # Create unified model table
                unified_model_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {self.schema_name}.unified_model (
                    id UUID PRIMARY KEY,
                    model_name VARCHAR(255) NOT NULL,
                    version VARCHAR(50) NOT NULL,
                    core_fields JSONB NOT NULL,
                    optional_fields JSONB NOT NULL,
                    field_mappings JSONB NOT NULL,
                    validation_rules JSONB,
                    created_from_sources JSONB NOT NULL,
                    confidence_score FLOAT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL
                );
                """
                conn.execute(text(unified_model_table_sql))
                
                # Create enriched data table
                enriched_data_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {self.schema_name}.enriched_data (
                    id UUID PRIMARY KEY,
                    original_data JSONB NOT NULL,
                    unified_data JSONB NOT NULL,
                    ontology_mappings JSONB NOT NULL,
                    enrichment_metadata JSONB,
                    confidence_score FLOAT NOT NULL,
                    enriched_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                """
                conn.execute(text(enriched_data_table_sql))
                
                # Create deduplicated data table
                deduplicated_data_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {self.schema_name}.deduplicated_data (
                    id UUID PRIMARY KEY,
                    canonical_entries JSONB NOT NULL,
                    duplicate_groups JSONB NOT NULL,
                    total_original_entries INTEGER NOT NULL,
                    total_canonical_entries INTEGER NOT NULL,
                    deduplication_metadata JSONB,
                    processed_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                """
                conn.execute(text(deduplicated_data_table_sql))
                
                conn.commit()
                logger.info("Database schema initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize database schema: {e}")
            raise
    
    def store_raw_data(self, data: RawPipelineData) -> StorageResult:
        """Store raw pipeline data in the database.
        
        Args:
            data: Raw pipeline data to store
            
        Returns:
            StorageResult with operation status
        """
        try:
            with self.engine.connect() as conn:
                # Check if data already exists (based on content hash)
                existing_check_sql = f"""
                SELECT id FROM {self.schema_name}.raw_pipeline_data 
                WHERE content_hash = :content_hash AND company = :company
                """
                
                existing = conn.execute(
                    text(existing_check_sql),
                    {
                        "content_hash": data.content.content_hash,
                        "company": data.source.company
                    }
                ).fetchone()
                
                if existing:
                    logger.info(f"Data already exists for {data.source.company} with hash {data.content.content_hash}")
                    return StorageResult(
                        success=True,
                        record_id=existing[0],
                        error_message="Data already exists (duplicate content hash)"
                    )
                
                # Insert new record
                insert_sql = f"""
                INSERT INTO {self.schema_name}.raw_pipeline_data (
                    id, company, source_url, collected_at, robots_compliance,
                    collection_agent, raw_html, extracted_data, parsing_method,
                    content_hash, validation_status, metadata
                ) VALUES (
                    :id, :company, :source_url, :collected_at, :robots_compliance,
                    :collection_agent, :raw_html, :extracted_data, :parsing_method,
                    :content_hash, :validation_status, :metadata
                )
                """
                
                # Prepare data for insertion
                insert_data = {
                    "id": str(data.id),
                    "company": data.source.company,
                    "source_url": str(data.source.url),
                    "collected_at": data.source.collected_at,
                    "robots_compliance": data.source.robots_compliance,
                    "collection_agent": data.source.collection_agent,
                    "raw_html": data.content.raw_html,
                    "extracted_data": json.dumps(data.content.extracted_data),
                    "parsing_method": data.content.parsing_method,
                    "content_hash": data.content.content_hash,
                    "validation_status": json.dumps(data.validation_status.model_dump()) if data.validation_status else None,
                    "metadata": json.dumps(data.metadata)
                }
                
                conn.execute(text(insert_sql), insert_data)
                
                # Record data lineage
                self._record_lineage(
                    conn, 
                    data.id, 
                    "raw_data_storage", 
                    {"source": data.source.company, "url": str(data.source.url)},
                    data.source.collection_agent
                )
                
                conn.commit()
                
                logger.info(f"Successfully stored raw data for {data.source.company} (ID: {data.id})")
                
                return StorageResult(
                    success=True,
                    record_id=data.id
                )
                
        except Exception as e:
            logger.error(f"Failed to store raw data: {e}")
            return StorageResult(
                success=False,
                error_message=str(e)
            )
    
    def retrieve_raw_data(
        self, 
        company: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[RawPipelineData]:
        """Retrieve raw pipeline data from the database.
        
        Args:
            company: Filter by company name
            start_date: Filter by collection start date
            end_date: Filter by collection end date
            limit: Maximum number of records to return
            
        Returns:
            List of RawPipelineData objects
        """
        try:
            with self.engine.connect() as conn:
                # Build query with filters
                where_clauses = []
                params = {"limit": limit}
                
                if company:
                    where_clauses.append("company = :company")
                    params["company"] = company
                
                if start_date:
                    where_clauses.append("collected_at >= :start_date")
                    params["start_date"] = start_date
                
                if end_date:
                    where_clauses.append("collected_at <= :end_date")
                    params["end_date"] = end_date
                
                where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
                
                query_sql = f"""
                SELECT * FROM {self.schema_name}.raw_pipeline_data 
                WHERE {where_clause}
                ORDER BY collected_at DESC
                LIMIT :limit
                """
                
                result = conn.execute(text(query_sql), params)
                rows = result.fetchall()
                
                # Convert rows to RawPipelineData objects
                pipeline_data = []
                for row in rows:
                    data = self._row_to_raw_pipeline_data(dict(row._mapping))
                    if data:
                        pipeline_data.append(data)
                
                logger.info(f"Retrieved {len(pipeline_data)} raw data records")
                return pipeline_data
                
        except Exception as e:
            logger.error(f"Failed to retrieve raw data: {e}")
            return []
    
    def get_data_by_id(self, record_id: UUID) -> Optional[RawPipelineData]:
        """Retrieve a specific raw data record by ID.
        
        Args:
            record_id: UUID of the record to retrieve
            
        Returns:
            RawPipelineData object or None if not found
        """
        try:
            with self.engine.connect() as conn:
                query_sql = f"""
                SELECT * FROM {self.schema_name}.raw_pipeline_data 
                WHERE id = :record_id
                """
                
                result = conn.execute(text(query_sql), {"record_id": str(record_id)})
                row = result.fetchone()
                
                if row:
                    return self._row_to_raw_pipeline_data(dict(row._mapping))
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve data by ID {record_id}: {e}")
            return None
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics.
        
        Returns:
            Dictionary with storage statistics
        """
        try:
            with self.engine.connect() as conn:
                stats_sql = f"""
                SELECT 
                    COUNT(*) as total_records,
                    COUNT(DISTINCT company) as unique_companies,
                    MIN(collected_at) as earliest_collection,
                    MAX(collected_at) as latest_collection,
                    AVG(LENGTH(raw_html)) as avg_content_length,
                    COUNT(CASE WHEN validation_status->>'is_valid' = 'true' THEN 1 END) as valid_records
                FROM {self.schema_name}.raw_pipeline_data
                """
                
                result = conn.execute(text(stats_sql))
                row = result.fetchone()
                
                if row:
                    return dict(row._mapping)
                
                return {}
                
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {}
    
    def _record_lineage(
        self, 
        conn, 
        record_id: UUID, 
        operation_type: str, 
        operation_details: Dict[str, Any],
        performed_by: str
    ):
        """Record data lineage information.
        
        Args:
            conn: Database connection
            record_id: ID of the record
            operation_type: Type of operation performed
            operation_details: Details about the operation
            performed_by: Who performed the operation
        """
        lineage_sql = f"""
        INSERT INTO {self.schema_name}.data_lineage (
            source_record_id, operation_type, operation_details, performed_by
        ) VALUES (
            :record_id, :operation_type, :operation_details, :performed_by
        )
        """
        
        conn.execute(text(lineage_sql), {
            "record_id": str(record_id),
            "operation_type": operation_type,
            "operation_details": json.dumps(operation_details),
            "performed_by": performed_by
        })
    
    def _row_to_raw_pipeline_data(self, row: Dict[str, Any]) -> Optional[RawPipelineData]:
        """Convert database row to RawPipelineData object.
        
        Args:
            row: Database row as dictionary
            
        Returns:
            RawPipelineData object or None if conversion fails
        """
        try:
            from ..models.pipeline_data import SourceMetadata, ContentData, ValidationResult
            from pydantic import HttpUrl
            from uuid import UUID
            
            # Parse validation status
            validation_status = None
            if row.get("validation_status"):
                validation_data = json.loads(row["validation_status"]) if isinstance(row["validation_status"], str) else row["validation_status"]
                validation_status = ValidationResult(**validation_data)
            
            # Parse extracted data
            extracted_data = json.loads(row["extracted_data"]) if isinstance(row["extracted_data"], str) else row["extracted_data"]
            
            # Parse metadata
            metadata = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
            
            return RawPipelineData(
                id=UUID(row["id"]),
                source=SourceMetadata(
                    company=row["company"],
                    url=HttpUrl(row["source_url"]),
                    collected_at=row["collected_at"],
                    robots_compliance=row["robots_compliance"],
                    collection_agent=row["collection_agent"]
                ),
                content=ContentData(
                    raw_html=row["raw_html"],
                    extracted_data=extracted_data,
                    parsing_method=row["parsing_method"],
                    content_hash=row["content_hash"]
                ),
                validation_status=validation_status,
                metadata=metadata,
                created_at=row.get("created_at", row["collected_at"])
            )
            
        except Exception as e:
            logger.error(f"Failed to convert row to RawPipelineData: {e}")
            return None
    
    def store_schema_analysis(self, schema_analysis: SchemaAnalysis) -> StorageResult:
        """Store schema analysis results.
        
        Args:
            schema_analysis: Schema analysis to store
            
        Returns:
            StorageResult with operation status
        """
        try:
            with self.engine.connect() as conn:
                insert_sql = f"""
                INSERT INTO {self.schema_name}.schema_analysis (
                    id, total_sources, schemas, common_fields, analysis_metadata, analyzed_at
                ) VALUES (
                    :id, :total_sources, :schemas, :common_fields, :analysis_metadata, :analyzed_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    total_sources = EXCLUDED.total_sources,
                    schemas = EXCLUDED.schemas,
                    common_fields = EXCLUDED.common_fields,
                    analysis_metadata = EXCLUDED.analysis_metadata,
                    analyzed_at = EXCLUDED.analyzed_at
                """
                
                conn.execute(text(insert_sql), {
                    "id": str(schema_analysis.id),
                    "total_sources": schema_analysis.total_sources,
                    "schemas": json.dumps([schema.model_dump() for schema in schema_analysis.schemas]),
                    "common_fields": json.dumps([field.model_dump() for field in schema_analysis.common_fields]),
                    "analysis_metadata": json.dumps(schema_analysis.analysis_metadata),
                    "analyzed_at": schema_analysis.analyzed_at
                })
                
                conn.commit()
                logger.info(f"Successfully stored schema analysis (ID: {schema_analysis.id})")
                
                return StorageResult(success=True, record_id=schema_analysis.id)
                
        except Exception as e:
            logger.error(f"Failed to store schema analysis: {e}")
            return StorageResult(success=False, error_message=str(e))
    
    def store_unified_model(self, unified_model: UnifiedDataModel) -> StorageResult:
        """Store unified data model.
        
        Args:
            unified_model: Unified model to store
            
        Returns:
            StorageResult with operation status
        """
        try:
            with self.engine.connect() as conn:
                insert_sql = f"""
                INSERT INTO {self.schema_name}.unified_model (
                    id, model_name, version, core_fields, optional_fields, 
                    field_mappings, validation_rules, created_from_sources, 
                    confidence_score, created_at
                ) VALUES (
                    :id, :model_name, :version, :core_fields, :optional_fields,
                    :field_mappings, :validation_rules, :created_from_sources,
                    :confidence_score, :created_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    model_name = EXCLUDED.model_name,
                    version = EXCLUDED.version,
                    core_fields = EXCLUDED.core_fields,
                    optional_fields = EXCLUDED.optional_fields,
                    field_mappings = EXCLUDED.field_mappings,
                    validation_rules = EXCLUDED.validation_rules,
                    created_from_sources = EXCLUDED.created_from_sources,
                    confidence_score = EXCLUDED.confidence_score,
                    created_at = EXCLUDED.created_at
                """
                
                conn.execute(text(insert_sql), {
                    "id": str(unified_model.id),
                    "model_name": unified_model.model_name,
                    "version": unified_model.version,
                    "core_fields": json.dumps({k: v.model_dump() for k, v in unified_model.core_fields.items()}),
                    "optional_fields": json.dumps({k: v.model_dump() for k, v in unified_model.optional_fields.items()}),
                    "field_mappings": json.dumps(unified_model.field_mappings),
                    "validation_rules": json.dumps(unified_model.validation_rules),
                    "created_from_sources": json.dumps(unified_model.created_from_sources),
                    "confidence_score": unified_model.confidence_score,
                    "created_at": unified_model.created_at
                })
                
                conn.commit()
                logger.info(f"Successfully stored unified model (ID: {unified_model.id})")
                
                return StorageResult(success=True, record_id=unified_model.id)
                
        except Exception as e:
            logger.error(f"Failed to store unified model: {e}")
            return StorageResult(success=False, error_message=str(e))
    
    def store_enriched_data(self, enriched_data: EnrichedData) -> StorageResult:
        """Store enriched data.
        
        Args:
            enriched_data: Enriched data to store
            
        Returns:
            StorageResult with operation status
        """
        try:
            with self.engine.connect() as conn:
                insert_sql = f"""
                INSERT INTO {self.schema_name}.enriched_data (
                    id, original_data, unified_data, ontology_mappings,
                    enrichment_metadata, confidence_score, enriched_at
                ) VALUES (
                    :id, :original_data, :unified_data, :ontology_mappings,
                    :enrichment_metadata, :confidence_score, :enriched_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    original_data = EXCLUDED.original_data,
                    unified_data = EXCLUDED.unified_data,
                    ontology_mappings = EXCLUDED.ontology_mappings,
                    enrichment_metadata = EXCLUDED.enrichment_metadata,
                    confidence_score = EXCLUDED.confidence_score,
                    enriched_at = EXCLUDED.enriched_at
                """
                
                conn.execute(text(insert_sql), {
                    "id": str(enriched_data.id),
                    "original_data": json.dumps(enriched_data.original_data),
                    "unified_data": json.dumps(enriched_data.unified_data),
                    "ontology_mappings": json.dumps([mapping.model_dump() for mapping in enriched_data.ontology_mappings]),
                    "enrichment_metadata": json.dumps(enriched_data.enrichment_metadata),
                    "confidence_score": enriched_data.confidence_score,
                    "enriched_at": enriched_data.enriched_at
                })
                
                conn.commit()
                logger.info(f"Successfully stored enriched data (ID: {enriched_data.id})")
                
                return StorageResult(success=True, record_id=enriched_data.id)
                
        except Exception as e:
            logger.error(f"Failed to store enriched data: {e}")
            return StorageResult(success=False, error_message=str(e))
    
    def store_deduplicated_data(self, deduplicated_data: DeduplicatedData) -> StorageResult:
        """Store deduplicated data.
        
        Args:
            deduplicated_data: Deduplicated data to store
            
        Returns:
            StorageResult with operation status
        """
        try:
            with self.engine.connect() as conn:
                insert_sql = f"""
                INSERT INTO {self.schema_name}.deduplicated_data (
                    id, canonical_entries, duplicate_groups, total_original_entries,
                    total_canonical_entries, deduplication_metadata, processed_at
                ) VALUES (
                    :id, :canonical_entries, :duplicate_groups, :total_original_entries,
                    :total_canonical_entries, :deduplication_metadata, :processed_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    canonical_entries = EXCLUDED.canonical_entries,
                    duplicate_groups = EXCLUDED.duplicate_groups,
                    total_original_entries = EXCLUDED.total_original_entries,
                    total_canonical_entries = EXCLUDED.total_canonical_entries,
                    deduplication_metadata = EXCLUDED.deduplication_metadata,
                    processed_at = EXCLUDED.processed_at
                """
                
                conn.execute(text(insert_sql), {
                    "id": str(deduplicated_data.id),
                    "canonical_entries": json.dumps([entry.model_dump() for entry in deduplicated_data.canonical_entries]),
                    "duplicate_groups": json.dumps([group.model_dump() for group in deduplicated_data.duplicate_groups]),
                    "total_original_entries": deduplicated_data.total_original_entries,
                    "total_canonical_entries": deduplicated_data.total_canonical_entries,
                    "deduplication_metadata": json.dumps(deduplicated_data.deduplication_metadata),
                    "processed_at": deduplicated_data.processed_at
                })
                
                conn.commit()
                logger.info(f"Successfully stored deduplicated data (ID: {deduplicated_data.id})")
                
                return StorageResult(success=True, record_id=deduplicated_data.id)
                
        except Exception as e:
            logger.error(f"Failed to store deduplicated data: {e}")
            return StorageResult(success=False, error_message=str(e))

    def close(self):
        """Close database connections."""
        if hasattr(self, 'engine'):
            self.engine.dispose()
            logger.info("Database connections closed")