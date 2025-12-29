"""Data Harmonizer Agent implementation using Strands framework."""

import logging
from typing import Dict, List, Optional

from strands import Agent

from ...models.harmonization import (
    DeduplicatedData,
    EnrichedData,
    SchemaAnalysis,
    UnifiedDataModel,
)
from ...models.pipeline_data import RawPipelineData
from ...storage.storage_manager import StorageManager
from .duplicate_resolver import DuplicateResolver
from .model_creator import UnifiedModelCreator
from .ontology_mapper import OntologyMapper
from .schema_analyzer import SchemaAnalyzer

logger = logging.getLogger(__name__)


class DataHarmonizerAgent:
    """Data Harmonizer Agent for schema analysis and data unification."""
    
    def __init__(self, storage_manager: Optional[StorageManager] = None, **kwargs):
        """Initialize the Data Harmonizer Agent.
        
        Args:
            storage_manager: Storage manager instance for data persistence
            **kwargs: Additional arguments for configuration
        """
        # Set default agent configuration
        self.name = kwargs.get('name', 'DataHarmonizerAgent')
        self.description = kwargs.get('description', 'Analyzes schemas and harmonizes pharmaceutical pipeline data')
        
        # Initialize components
        self.schema_analyzer = SchemaAnalyzer()
        self.model_creator = UnifiedModelCreator()
        self.ontology_mapper = OntologyMapper()
        self.duplicate_resolver = DuplicateResolver()
        self.storage_manager = storage_manager
        
        # Cache for unified models to avoid recomputation
        self._unified_model_cache = {}
        
        logger.info(f"Initialized {self.name} with schema analysis and harmonization capabilities")
    
    async def analyze_schemas_from_raw_data(self, raw_data_list: List[RawPipelineData]) -> Dict:
        """Analyze schemas from raw pipeline data.
        
        Args:
            raw_data_list: List of raw pipeline data from different sources
            
        Returns:
            Dictionary with schema analysis results
        """
        try:
            logger.info(f"Analyzing schemas from {len(raw_data_list)} raw data sources")
            
            # Perform schema analysis
            schema_analysis = self.analyze_schema(raw_data_list)
            
            # Store schema analysis if storage manager is available
            if self.storage_manager:
                try:
                    storage_result = self.storage_manager.store_schema_analysis(schema_analysis)
                    logger.info(f"Stored schema analysis: {storage_result.success}")
                except Exception as e:
                    logger.warning(f"Failed to store schema analysis: {e}")
            
            return {
                "action": "analyze_schemas",
                "schema_analysis": schema_analysis.model_dump(),
                "total_sources": schema_analysis.total_sources,
                "common_fields_count": len(schema_analysis.common_fields),
                "success": True
            }
            
        except Exception as e:
            error_msg = f"Failed to analyze schemas: {e}"
            logger.error(error_msg)
            return {
                "action": "analyze_schemas",
                "error": error_msg,
                "success": False
            }
    
    async def create_unified_model_from_analysis(self, schema_analysis: SchemaAnalysis) -> Dict:
        """Create unified data model from schema analysis.
        
        Args:
            schema_analysis: Results from schema analysis
            
        Returns:
            Dictionary with unified model creation results
        """
        try:
            logger.info("Creating unified data model from schema analysis")
            
            # Create unified model
            unified_model = self.create_unified_model(schema_analysis)
            
            # Cache the model for future use
            cache_key = f"model_{schema_analysis.id}"
            self._unified_model_cache[cache_key] = unified_model
            
            # Store unified model if storage manager is available
            if self.storage_manager:
                try:
                    storage_result = self.storage_manager.store_unified_model(unified_model)
                    logger.info(f"Stored unified model: {storage_result.success}")
                except Exception as e:
                    logger.warning(f"Failed to store unified model: {e}")
            
            return {
                "action": "create_unified_model",
                "unified_model": unified_model.model_dump(),
                "core_fields_count": len(unified_model.core_fields),
                "optional_fields_count": len(unified_model.optional_fields),
                "confidence_score": unified_model.confidence_score,
                "success": True
            }
            
        except Exception as e:
            error_msg = f"Failed to create unified model: {e}"
            logger.error(error_msg)
            return {
                "action": "create_unified_model",
                "error": error_msg,
                "success": False
            }
    
    async def apply_ontology_mappings(self, raw_data_list: List[RawPipelineData], unified_model: UnifiedDataModel) -> Dict:
        """Apply ontology mappings to raw data using unified model.
        
        Args:
            raw_data_list: List of raw pipeline data
            unified_model: Unified data model for transformation
            
        Returns:
            Dictionary with ontology mapping results
        """
        try:
            logger.info(f"Applying ontology mappings to {len(raw_data_list)} data sources")
            
            enriched_data_list = []
            
            for raw_data in raw_data_list:
                # Apply ontologies to transform data
                enriched_data = self.apply_ontologies(raw_data, unified_model)
                enriched_data_list.append(enriched_data)
            
            # Store enriched data if storage manager is available
            if self.storage_manager:
                try:
                    for enriched_data in enriched_data_list:
                        storage_result = self.storage_manager.store_enriched_data(enriched_data)
                        logger.debug(f"Stored enriched data: {storage_result.success}")
                except Exception as e:
                    logger.warning(f"Failed to store enriched data: {e}")
            
            return {
                "action": "apply_ontology_mappings",
                "enriched_data": [data.model_dump() for data in enriched_data_list],
                "total_enriched": len(enriched_data_list),
                "average_confidence": sum(data.confidence_score for data in enriched_data_list) / len(enriched_data_list),
                "success": True
            }
            
        except Exception as e:
            error_msg = f"Failed to apply ontology mappings: {e}"
            logger.error(error_msg)
            return {
                "action": "apply_ontology_mappings",
                "error": error_msg,
                "success": False
            }
    
    async def resolve_duplicates_and_enrich(self, enriched_data_list: List[EnrichedData]) -> Dict:
        """Resolve duplicates and enrich data with additional metadata.
        
        Args:
            enriched_data_list: List of enriched data entries
            
        Returns:
            Dictionary with duplicate resolution results
        """
        try:
            logger.info(f"Resolving duplicates in {len(enriched_data_list)} enriched data entries")
            
            # Resolve duplicates
            deduplicated_data = self.resolve_duplicates(enriched_data_list)
            
            # Store deduplicated data if storage manager is available
            if self.storage_manager:
                try:
                    storage_result = self.storage_manager.store_deduplicated_data(deduplicated_data)
                    logger.info(f"Stored deduplicated data: {storage_result.success}")
                except Exception as e:
                    logger.warning(f"Failed to store deduplicated data: {e}")
            
            return {
                "action": "resolve_duplicates",
                "deduplicated_data": deduplicated_data.model_dump(),
                "original_entries": deduplicated_data.total_original_entries,
                "canonical_entries": deduplicated_data.total_canonical_entries,
                "duplicate_groups": len(deduplicated_data.duplicate_groups),
                "deduplication_rate": (deduplicated_data.total_original_entries - deduplicated_data.total_canonical_entries) / deduplicated_data.total_original_entries if deduplicated_data.total_original_entries > 0 else 0.0,
                "success": True
            }
            
        except Exception as e:
            error_msg = f"Failed to resolve duplicates: {e}"
            logger.error(error_msg)
            return {
                "action": "resolve_duplicates",
                "error": error_msg,
                "success": False
            }
    
    async def harmonize_complete_pipeline(self, raw_data_list: List[RawPipelineData]) -> Dict:
        """Complete harmonization pipeline from raw data to deduplicated unified data.
        
        Args:
            raw_data_list: List of raw pipeline data from different sources
            
        Returns:
            Dictionary with complete harmonization results
        """
        try:
            logger.info(f"Starting complete harmonization pipeline for {len(raw_data_list)} sources")
            
            # Step 1: Analyze schemas
            schema_analysis = self.analyze_schema(raw_data_list)
            logger.info(f"Schema analysis complete: {len(schema_analysis.common_fields)} common fields")
            
            # Step 2: Create unified model
            unified_model = self.create_unified_model(schema_analysis)
            logger.info(f"Unified model created with confidence: {unified_model.confidence_score:.3f}")
            
            # Step 3: Apply ontologies and transform data
            enriched_data_list = []
            for raw_data in raw_data_list:
                enriched_data = self.apply_ontologies(raw_data, unified_model)
                enriched_data_list.append(enriched_data)
            logger.info(f"Ontology mapping complete: {len(enriched_data_list)} enriched entries")
            
            # Step 4: Resolve duplicates
            deduplicated_data = self.resolve_duplicates(enriched_data_list)
            logger.info(f"Duplicate resolution complete: {deduplicated_data.total_canonical_entries} canonical entries")
            
            # Store all results if storage manager is available
            if self.storage_manager:
                try:
                    self.storage_manager.store_schema_analysis(schema_analysis)
                    self.storage_manager.store_unified_model(unified_model)
                    for enriched_data in enriched_data_list:
                        self.storage_manager.store_enriched_data(enriched_data)
                    self.storage_manager.store_deduplicated_data(deduplicated_data)
                    logger.info("All harmonization results stored successfully")
                except Exception as e:
                    logger.warning(f"Failed to store some harmonization results: {e}")
            
            return {
                "action": "complete_harmonization",
                "schema_analysis": schema_analysis.model_dump(),
                "unified_model": unified_model.model_dump(),
                "enriched_data_count": len(enriched_data_list),
                "deduplicated_data": deduplicated_data.model_dump(),
                "pipeline_summary": {
                    "original_sources": len(raw_data_list),
                    "common_fields_identified": len(schema_analysis.common_fields),
                    "model_confidence": unified_model.confidence_score,
                    "original_entries": deduplicated_data.total_original_entries,
                    "final_canonical_entries": deduplicated_data.total_canonical_entries,
                    "deduplication_rate": (deduplicated_data.total_original_entries - deduplicated_data.total_canonical_entries) / deduplicated_data.total_original_entries if deduplicated_data.total_original_entries > 0 else 0.0
                },
                "success": True
            }
            
        except Exception as e:
            error_msg = f"Complete harmonization pipeline failed: {e}"
            logger.error(error_msg)
            return {
                "action": "complete_harmonization",
                "error": error_msg,
                "success": False
            }
    
    def analyze_schema(self, raw_data_list: List[RawPipelineData]) -> SchemaAnalysis:
        """Analyze schemas from raw pipeline data.
        
        Args:
            raw_data_list: List of raw pipeline data
            
        Returns:
            SchemaAnalysis with identified schemas and common fields
        """
        return self.schema_analyzer.analyze_schemas(raw_data_list)
    
    def create_unified_model(self, schema_analysis: SchemaAnalysis) -> UnifiedDataModel:
        """Create unified data model from schema analysis.
        
        Args:
            schema_analysis: Results from schema analysis
            
        Returns:
            UnifiedDataModel that accommodates all source variations
        """
        return self.model_creator.create_unified_model(schema_analysis)
    
    def apply_ontologies(self, raw_data: RawPipelineData, unified_model: UnifiedDataModel) -> EnrichedData:
        """Apply ontology mappings to raw data.
        
        Args:
            raw_data: Raw pipeline data to enrich
            unified_model: Unified model for transformation
            
        Returns:
            EnrichedData with ontology mappings applied
        """
        return self.ontology_mapper.apply_ontologies(raw_data, unified_model)
    
    def resolve_duplicates(self, enriched_data_list: List[EnrichedData]) -> DeduplicatedData:
        """Resolve duplicate entries in enriched data.
        
        Args:
            enriched_data_list: List of enriched data entries
            
        Returns:
            DeduplicatedData with resolved duplicates
        """
        return self.duplicate_resolver.resolve_duplicates(enriched_data_list)
    
    def get_cached_unified_model(self, schema_analysis_id: str) -> Optional[UnifiedDataModel]:
        """Get cached unified model by schema analysis ID.
        
        Args:
            schema_analysis_id: ID of the schema analysis
            
        Returns:
            Cached UnifiedDataModel or None if not found
        """
        cache_key = f"model_{schema_analysis_id}"
        return self._unified_model_cache.get(cache_key)
    
    def clear_cache(self):
        """Clear the unified model cache."""
        self._unified_model_cache.clear()
        logger.info("Unified model cache cleared")