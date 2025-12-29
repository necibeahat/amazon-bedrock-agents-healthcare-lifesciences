"""Schema analysis component for the Data Harmonizer Agent."""

import hashlib
import logging
from collections import Counter, defaultdict
from typing import Any, Dict, List, Set

from ...models.harmonization import CommonField, FieldInfo, Schema, SchemaAnalysis
from ...models.pipeline_data import RawPipelineData

logger = logging.getLogger(__name__)


class SchemaAnalyzer:
    """Analyzes schemas from raw pipeline data to identify common fields."""
    
    def __init__(self):
        """Initialize the schema analyzer."""
        self.pharmaceutical_field_patterns = {
            # Compound/Drug related fields
            'compound_name': ['compound', 'drug', 'product', 'name', 'title', 'molecule'],
            'compound_type': ['type', 'class', 'category', 'modality'],
            'mechanism_of_action': ['mechanism', 'moa', 'action', 'target', 'pathway'],
            
            # Indication/Disease related fields
            'indication': ['indication', 'disease', 'condition', 'disorder', 'therapeutic_area'],
            'therapeutic_area': ['therapeutic', 'area', 'specialty', 'field', 'domain'],
            
            # Development phase fields
            'development_phase': ['phase', 'stage', 'status', 'development'],
            'regulatory_status': ['regulatory', 'approval', 'designation', 'status'],
            
            # Timeline fields
            'estimated_completion': ['completion', 'timeline', 'expected', 'projected', 'date'],
            'last_updated': ['updated', 'modified', 'changed', 'revised'],
            
            # Company/Organization fields
            'company': ['company', 'organization', 'sponsor', 'developer'],
            'division': ['division', 'unit', 'department', 'subsidiary'],
            
            # Additional metadata
            'description': ['description', 'summary', 'overview', 'details'],
            'url': ['url', 'link', 'reference', 'source'],
            'id': ['id', 'identifier', 'key', 'uuid']
        }
    
    def analyze_schemas(self, raw_data_list: List[RawPipelineData]) -> SchemaAnalysis:
        """Analyze schemas from multiple raw data sources.
        
        Args:
            raw_data_list: List of raw pipeline data from different sources
            
        Returns:
            SchemaAnalysis with identified schemas and common fields
        """
        logger.info(f"Analyzing schemas from {len(raw_data_list)} data sources")
        
        schemas = []
        all_fields_by_source = {}
        
        # Analyze each source individually
        for raw_data in raw_data_list:
            try:
                schema = self._analyze_single_source(raw_data)
                schemas.append(schema)
                all_fields_by_source[schema.source_company] = schema.fields
                logger.info(f"Analyzed schema for {schema.source_company}: {len(schema.fields)} fields")
                
            except Exception as e:
                logger.error(f"Failed to analyze schema for {raw_data.source.company}: {e}")
                continue
        
        # Identify common fields across sources
        common_fields = self._identify_common_fields(all_fields_by_source)
        
        analysis = SchemaAnalysis(
            schemas=schemas,
            common_fields=common_fields,
            total_sources=len(schemas),
            analysis_metadata={
                'total_raw_sources': len(raw_data_list),
                'successful_analyses': len(schemas),
                'failed_analyses': len(raw_data_list) - len(schemas),
                'common_fields_count': len(common_fields),
                'analyzer_version': '1.0'
            }
        )
        
        logger.info(f"Schema analysis complete: {len(common_fields)} common fields identified")
        return analysis
    
    def _analyze_single_source(self, raw_data: RawPipelineData) -> Schema:
        """Analyze schema for a single data source.
        
        Args:
            raw_data: Raw pipeline data from a single source
            
        Returns:
            Schema object with field information
        """
        pipeline_entries = raw_data.content.extracted_data.get('pipeline_entries', [])
        
        if not pipeline_entries:
            logger.warning(f"No pipeline entries found for {raw_data.source.company}")
            pipeline_entries = [raw_data.content.extracted_data]  # Use the entire extracted data
        
        # Collect field information
        field_stats = defaultdict(lambda: {
            'data_types': Counter(),
            'sample_values': [],
            'frequency': 0,
            'null_count': 0,
            'unique_values': set()
        })
        
        total_records = len(pipeline_entries)
        
        # Analyze each entry
        for entry in pipeline_entries:
            if not isinstance(entry, dict):
                continue
                
            for field_name, value in entry.items():
                stats = field_stats[field_name]
                stats['frequency'] += 1
                
                if value is None or value == '' or value == 'N/A':
                    stats['null_count'] += 1
                else:
                    # Determine data type
                    data_type = self._get_data_type(value)
                    stats['data_types'][data_type] += 1
                    
                    # Collect sample values (limit to 10)
                    if len(stats['sample_values']) < 10:
                        stats['sample_values'].append(value)
                    
                    # Track unique values (limit to 1000 for memory)
                    if len(stats['unique_values']) < 1000:
                        stats['unique_values'].add(str(value))
        
        # Convert to FieldInfo objects
        fields = []
        for field_name, stats in field_stats.items():
            # Get most common data type
            most_common_type = stats['data_types'].most_common(1)
            data_type = most_common_type[0][0] if most_common_type else 'unknown'
            
            field_info = FieldInfo(
                name=field_name,
                data_type=data_type,
                sample_values=stats['sample_values'][:5],  # Keep only first 5 samples
                frequency=stats['frequency'],
                null_count=stats['null_count'],
                unique_count=len(stats['unique_values']),
                description=self._generate_field_description(field_name, stats)
            )
            fields.append(field_info)
        
        # Calculate schema hash for change detection
        schema_content = f"{raw_data.source.company}:{len(fields)}:{sorted([f.name for f in fields])}"
        schema_hash = hashlib.md5(schema_content.encode()).hexdigest()
        
        # Calculate confidence score based on data quality
        confidence_score = self._calculate_schema_confidence(fields, total_records)
        
        return Schema(
            source_company=raw_data.source.company,
            source_url=str(raw_data.source.url),
            fields=fields,
            total_records=total_records,
            schema_hash=schema_hash,
            confidence_score=confidence_score
        )
    
    def _identify_common_fields(self, all_fields_by_source: Dict[str, List[FieldInfo]]) -> List[CommonField]:
        """Identify common fields across multiple sources.
        
        Args:
            all_fields_by_source: Dictionary mapping source company to list of fields
            
        Returns:
            List of CommonField objects
        """
        if not all_fields_by_source:
            return []
        
        # Group fields by semantic similarity
        field_groups = defaultdict(lambda: {
            'sources': {},  # source -> field_name
            'sample_values': [],
            'data_types': Counter()
        })
        
        # Analyze each source's fields
        for source, fields in all_fields_by_source.items():
            for field in fields:
                # Find the best matching canonical field
                canonical_name = self._find_canonical_field_name(field.name)
                
                group = field_groups[canonical_name]
                group['sources'][source] = field.name
                group['sample_values'].extend(field.sample_values)
                group['data_types'][field.data_type] += field.frequency
        
        # Convert to CommonField objects
        common_fields = []
        total_sources = len(all_fields_by_source)
        
        for canonical_name, group in field_groups.items():
            # Only include fields that appear in at least 2 sources or are core pharmaceutical fields
            coverage = len(group['sources']) / total_sources
            is_core_field = canonical_name in self.pharmaceutical_field_patterns
            
            if coverage >= 0.5 or (is_core_field and coverage > 0):
                # Get most common data type
                most_common_type = group['data_types'].most_common(1)
                field_type = most_common_type[0][0] if most_common_type else 'string'
                
                common_field = CommonField(
                    canonical_name=canonical_name,
                    field_type=field_type,
                    source_mappings=group['sources'],
                    coverage=coverage,
                    description=self._generate_common_field_description(canonical_name, group),
                    sample_values=group['sample_values'][:10]  # Keep top 10 samples
                )
                common_fields.append(common_field)
        
        # Sort by coverage (most common fields first)
        common_fields.sort(key=lambda x: x.coverage, reverse=True)
        
        return common_fields
    
    def _find_canonical_field_name(self, field_name: str) -> str:
        """Find the canonical name for a field based on pharmaceutical patterns.
        
        Args:
            field_name: Original field name
            
        Returns:
            Canonical field name
        """
        field_lower = field_name.lower().replace('_', ' ').replace('-', ' ')
        
        # Check against pharmaceutical field patterns
        for canonical_name, patterns in self.pharmaceutical_field_patterns.items():
            for pattern in patterns:
                if pattern in field_lower:
                    return canonical_name
        
        # If no pattern matches, use a cleaned version of the original name
        return field_name.lower().replace(' ', '_').replace('-', '_')
    
    def _get_data_type(self, value: Any) -> str:
        """Determine the data type of a value.
        
        Args:
            value: Value to analyze
            
        Returns:
            String representation of data type
        """
        if value is None:
            return 'null'
        elif isinstance(value, bool):
            return 'boolean'
        elif isinstance(value, int):
            return 'integer'
        elif isinstance(value, float):
            return 'float'
        elif isinstance(value, list):
            return 'array'
        elif isinstance(value, dict):
            return 'object'
        elif isinstance(value, str):
            # Try to detect more specific string types
            value_lower = value.lower().strip()
            
            # Check for URLs
            if value_lower.startswith(('http://', 'https://', 'www.')):
                return 'url'
            
            # Check for dates (simple patterns)
            if any(pattern in value for pattern in ['2023', '2024', '2025', '/', '-']):
                if len(value) <= 20:  # Reasonable date length
                    return 'date'
            
            # Check for phases
            if any(phase in value_lower for phase in ['phase', 'stage', 'preclinical', 'clinical']):
                return 'phase'
            
            return 'string'
        else:
            return 'unknown'
    
    def _generate_field_description(self, field_name: str, stats: Dict) -> str:
        """Generate a description for a field based on its statistics.
        
        Args:
            field_name: Name of the field
            stats: Statistics about the field
            
        Returns:
            Generated description
        """
        canonical_name = self._find_canonical_field_name(field_name)
        
        # Base description from canonical name
        descriptions = {
            'compound_name': 'Name of the pharmaceutical compound or drug',
            'indication': 'Medical condition or disease being treated',
            'development_phase': 'Current phase of clinical development',
            'therapeutic_area': 'Medical specialty or therapeutic domain',
            'mechanism_of_action': 'How the drug works at molecular level',
            'company': 'Pharmaceutical company developing the compound',
            'regulatory_status': 'Current regulatory approval status'
        }
        
        base_desc = descriptions.get(canonical_name, f"Field containing {canonical_name.replace('_', ' ')}")
        
        # Add statistics
        if stats['frequency'] > 0:
            completeness = (stats['frequency'] - stats['null_count']) / stats['frequency']
            if completeness < 0.5:
                base_desc += " (often missing)"
            elif completeness > 0.9:
                base_desc += " (usually present)"
        
        return base_desc
    
    def _generate_common_field_description(self, canonical_name: str, group: Dict) -> str:
        """Generate description for a common field.
        
        Args:
            canonical_name: Canonical name of the field
            group: Field group information
            
        Returns:
            Generated description
        """
        base_desc = self._generate_field_description(canonical_name, {'frequency': 1, 'null_count': 0})
        
        # Add source information
        sources = list(group['sources'].keys())
        if len(sources) == 1:
            base_desc += f" (from {sources[0]})"
        else:
            base_desc += f" (from {len(sources)} sources: {', '.join(sources[:3])}{'...' if len(sources) > 3 else ''})"
        
        return base_desc
    
    def _calculate_schema_confidence(self, fields: List[FieldInfo], total_records: int) -> float:
        """Calculate confidence score for a schema.
        
        Args:
            fields: List of fields in the schema
            total_records: Total number of records analyzed
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not fields or total_records == 0:
            return 0.0
        
        # Base confidence from number of fields
        field_score = min(1.0, len(fields) / 10.0)  # Expect at least 10 fields for full score
        
        # Data quality score
        quality_scores = []
        for field in fields:
            if field.frequency > 0:
                completeness = (field.frequency - field.null_count) / field.frequency
                quality_scores.append(completeness)
        
        quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        
        # Record count score
        record_score = min(1.0, total_records / 50.0)  # Expect at least 50 records for full score
        
        # Pharmaceutical field coverage score
        pharma_fields_found = 0
        for field in fields:
            canonical_name = self._find_canonical_field_name(field.name)
            if canonical_name in self.pharmaceutical_field_patterns:
                pharma_fields_found += 1
        
        pharma_score = min(1.0, pharma_fields_found / 5.0)  # Expect at least 5 pharma fields
        
        # Weighted average
        confidence = (
            field_score * 0.2 +
            quality_score * 0.3 +
            record_score * 0.2 +
            pharma_score * 0.3
        )
        
        return round(confidence, 3)