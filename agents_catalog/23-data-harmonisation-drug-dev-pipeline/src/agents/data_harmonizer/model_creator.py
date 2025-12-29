"""Unified data model creation component for the Data Harmonizer Agent."""

import logging
from typing import Any, Dict, List

from ...models.harmonization import (
    CommonField,
    FieldInfo,
    SchemaAnalysis,
    UnifiedDataModel,
)

logger = logging.getLogger(__name__)


class UnifiedModelCreator:
    """Creates unified data models from schema analysis results."""
    
    def __init__(self):
        """Initialize the unified model creator."""
        # Standard pharmaceutical pipeline fields with their specifications
        self.standard_pharma_fields = {
            # Core compound information
            'compound_name': {
                'type': 'string',
                'required': True,
                'description': 'Name of the pharmaceutical compound or drug',
                'validation': {'min_length': 1, 'max_length': 200}
            },
            'compound_type': {
                'type': 'string',
                'required': False,
                'description': 'Type or class of the compound (e.g., small molecule, biologic)',
                'validation': {'enum': ['small_molecule', 'biologic', 'vaccine', 'gene_therapy', 'cell_therapy', 'other']}
            },
            'mechanism_of_action': {
                'type': 'string',
                'required': False,
                'description': 'How the drug works at the molecular level',
                'validation': {'max_length': 500}
            },
            
            # Indication and therapeutic area
            'indication': {
                'type': 'string',
                'required': True,
                'description': 'Primary medical condition or disease being treated',
                'validation': {'min_length': 1, 'max_length': 300}
            },
            'secondary_indications': {
                'type': 'array',
                'required': False,
                'description': 'Additional indications being investigated',
                'validation': {'item_type': 'string', 'max_items': 10}
            },
            'therapeutic_area': {
                'type': 'string',
                'required': False,
                'description': 'Medical specialty or therapeutic domain',
                'validation': {'max_length': 100}
            },
            
            # Development status
            'development_phase': {
                'type': 'string',
                'required': True,
                'description': 'Current phase of clinical development',
                'validation': {
                    'enum': [
                        'discovery', 'preclinical', 'phase_1', 'phase_2', 'phase_3',
                        'registration', 'approved', 'launched', 'discontinued'
                    ]
                }
            },
            'regulatory_status': {
                'type': 'string',
                'required': False,
                'description': 'Current regulatory approval status',
                'validation': {'max_length': 200}
            },
            'regulatory_designations': {
                'type': 'array',
                'required': False,
                'description': 'Special regulatory designations (e.g., breakthrough therapy)',
                'validation': {'item_type': 'string', 'max_items': 5}
            },
            
            # Timeline information
            'estimated_completion': {
                'type': 'date',
                'required': False,
                'description': 'Estimated completion date for current phase',
                'validation': {'format': 'date'}
            },
            'last_updated': {
                'type': 'date',
                'required': False,
                'description': 'Date when information was last updated',
                'validation': {'format': 'date'}
            },
            
            # Company information
            'company': {
                'type': 'string',
                'required': True,
                'description': 'Pharmaceutical company developing the compound',
                'validation': {'min_length': 1, 'max_length': 100}
            },
            'division': {
                'type': 'string',
                'required': False,
                'description': 'Company division or subsidiary',
                'validation': {'max_length': 100}
            },
            
            # Additional metadata
            'description': {
                'type': 'string',
                'required': False,
                'description': 'Detailed description of the compound or program',
                'validation': {'max_length': 1000}
            },
            'source_url': {
                'type': 'url',
                'required': False,
                'description': 'URL where the information was obtained',
                'validation': {'format': 'url'}
            },
            'internal_id': {
                'type': 'string',
                'required': False,
                'description': 'Internal identifier used by the company',
                'validation': {'max_length': 50}
            }
        }
    
    def create_unified_model(self, schema_analysis: SchemaAnalysis) -> UnifiedDataModel:
        """Create a unified data model from schema analysis results.
        
        Args:
            schema_analysis: Results from schema analysis
            
        Returns:
            UnifiedDataModel that accommodates all source variations
        """
        logger.info(f"Creating unified model from {schema_analysis.total_sources} sources")
        
        # Start with standard pharmaceutical fields
        core_fields = self._create_core_fields()
        optional_fields = {}
        field_mappings = {}
        
        # Process each source to create field mappings
        for schema in schema_analysis.schemas:
            source_mappings = {}
            
            # Map source fields to unified model fields
            for field in schema.fields:
                unified_field_name = self._map_to_unified_field(field, schema_analysis.common_fields)
                
                if unified_field_name in core_fields:
                    # Map to core field
                    source_mappings[field.name] = unified_field_name
                else:
                    # Add as optional field
                    if unified_field_name not in optional_fields:
                        optional_fields[unified_field_name] = self._create_field_info_from_source(
                            field, unified_field_name
                        )
                    source_mappings[field.name] = unified_field_name
            
            field_mappings[schema.source_company] = source_mappings
        
        # Create validation rules
        validation_rules = self._create_validation_rules(core_fields, optional_fields)
        
        # Calculate confidence score
        confidence_score = self._calculate_model_confidence(
            schema_analysis, core_fields, optional_fields
        )
        
        unified_model = UnifiedDataModel(
            core_fields=core_fields,
            optional_fields=optional_fields,
            field_mappings=field_mappings,
            validation_rules=validation_rules,
            created_from_sources=[schema.source_company for schema in schema_analysis.schemas],
            confidence_score=confidence_score
        )
        
        logger.info(
            f"Created unified model with {len(core_fields)} core fields, "
            f"{len(optional_fields)} optional fields, confidence: {confidence_score:.3f}"
        )
        
        return unified_model
    
    def _create_core_fields(self) -> Dict[str, FieldInfo]:
        """Create core pharmaceutical pipeline fields.
        
        Returns:
            Dictionary of core FieldInfo objects
        """
        core_fields = {}
        
        for field_name, spec in self.standard_pharma_fields.items():
            field_info = FieldInfo(
                name=field_name,
                data_type=spec['type'],
                sample_values=[],
                frequency=0,
                null_count=0,
                unique_count=0,
                description=spec['description']
            )
            core_fields[field_name] = field_info
        
        return core_fields
    
    def _map_to_unified_field(self, source_field: FieldInfo, common_fields: List[CommonField]) -> str:
        """Map a source field to a unified field name.
        
        Args:
            source_field: Field from source schema
            common_fields: List of identified common fields
            
        Returns:
            Unified field name
        """
        # First, check if this field is already identified as a common field
        for common_field in common_fields:
            for source, field_name in common_field.source_mappings.items():
                if field_name == source_field.name:
                    return common_field.canonical_name
        
        # If not found in common fields, try to map to standard pharmaceutical fields
        field_lower = source_field.name.lower().replace('_', ' ').replace('-', ' ')
        
        # Direct mapping patterns
        direct_mappings = {
            'name': 'compound_name',
            'title': 'compound_name',
            'product': 'compound_name',
            'drug': 'compound_name',
            'compound': 'compound_name',
            'molecule': 'compound_name',
            
            'disease': 'indication',
            'condition': 'indication',
            'disorder': 'indication',
            'target': 'indication',
            
            'phase': 'development_phase',
            'stage': 'development_phase',
            'status': 'development_phase',
            
            'area': 'therapeutic_area',
            'specialty': 'therapeutic_area',
            'field': 'therapeutic_area',
            
            'sponsor': 'company',
            'developer': 'company',
            'organization': 'company',
            
            'moa': 'mechanism_of_action',
            'target': 'mechanism_of_action',
            'pathway': 'mechanism_of_action',
            
            'url': 'source_url',
            'link': 'source_url',
            'reference': 'source_url',
            
            'id': 'internal_id',
            'identifier': 'internal_id',
            'key': 'internal_id'
        }
        
        # Check for direct mappings
        for pattern, unified_name in direct_mappings.items():
            if pattern in field_lower:
                return unified_name
        
        # If no mapping found, create a cleaned field name
        cleaned_name = source_field.name.lower().replace(' ', '_').replace('-', '_')
        return cleaned_name
    
    def _create_field_info_from_source(self, source_field: FieldInfo, unified_name: str) -> FieldInfo:
        """Create a FieldInfo object for the unified model from a source field.
        
        Args:
            source_field: Original field from source
            unified_name: Name in unified model
            
        Returns:
            FieldInfo for unified model
        """
        return FieldInfo(
            name=unified_name,
            data_type=source_field.data_type,
            sample_values=source_field.sample_values,
            frequency=source_field.frequency,
            null_count=source_field.null_count,
            unique_count=source_field.unique_count,
            description=source_field.description or f"Field mapped from source: {source_field.name}"
        )
    
    def _create_validation_rules(
        self, 
        core_fields: Dict[str, FieldInfo], 
        optional_fields: Dict[str, FieldInfo]
    ) -> Dict[str, Any]:
        """Create validation rules for the unified model.
        
        Args:
            core_fields: Core fields in the model
            optional_fields: Optional fields in the model
            
        Returns:
            Dictionary of validation rules
        """
        validation_rules = {
            'required_fields': [],
            'field_types': {},
            'field_constraints': {},
            'business_rules': []
        }
        
        # Add required fields from standard pharmaceutical fields
        for field_name, spec in self.standard_pharma_fields.items():
            if field_name in core_fields and spec.get('required', False):
                validation_rules['required_fields'].append(field_name)
            
            if field_name in core_fields:
                validation_rules['field_types'][field_name] = spec['type']
                if 'validation' in spec:
                    validation_rules['field_constraints'][field_name] = spec['validation']
        
        # Add business rules
        validation_rules['business_rules'] = [
            {
                'name': 'compound_name_not_empty',
                'description': 'Compound name must not be empty',
                'rule': 'compound_name is not null and len(compound_name.strip()) > 0'
            },
            {
                'name': 'valid_development_phase',
                'description': 'Development phase must be a valid pharmaceutical phase',
                'rule': 'development_phase in valid_phases'
            },
            {
                'name': 'company_not_empty',
                'description': 'Company name must not be empty',
                'rule': 'company is not null and len(company.strip()) > 0'
            },
            {
                'name': 'indication_not_empty',
                'description': 'Primary indication must not be empty',
                'rule': 'indication is not null and len(indication.strip()) > 0'
            }
        ]
        
        return validation_rules
    
    def _calculate_model_confidence(
        self,
        schema_analysis: SchemaAnalysis,
        core_fields: Dict[str, FieldInfo],
        optional_fields: Dict[str, FieldInfo]
    ) -> float:
        """Calculate confidence score for the unified model.
        
        Args:
            schema_analysis: Original schema analysis
            core_fields: Core fields in unified model
            optional_fields: Optional fields in unified model
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not schema_analysis.schemas:
            return 0.0
        
        # Source quality score (average of individual schema confidence scores)
        source_scores = [schema.confidence_score for schema in schema_analysis.schemas]
        source_quality = sum(source_scores) / len(source_scores)
        
        # Field coverage score (how many standard pharma fields we can map)
        total_standard_fields = len(self.standard_pharma_fields)
        mapped_standard_fields = 0
        
        for schema in schema_analysis.schemas:
            for field in schema.fields:
                unified_name = self._map_to_unified_field(field, schema_analysis.common_fields)
                if unified_name in self.standard_pharma_fields:
                    mapped_standard_fields += 1
                    break  # Count each standard field only once
        
        field_coverage = min(1.0, mapped_standard_fields / total_standard_fields)
        
        # Common field score (how many fields are common across sources)
        if schema_analysis.total_sources > 1:
            high_coverage_fields = sum(1 for cf in schema_analysis.common_fields if cf.coverage >= 0.7)
            total_common_fields = len(schema_analysis.common_fields)
            common_field_score = high_coverage_fields / total_common_fields if total_common_fields > 0 else 0.0
        else:
            common_field_score = 0.5  # Single source gets neutral score
        
        # Model completeness score
        total_fields = len(core_fields) + len(optional_fields)
        completeness_score = min(1.0, total_fields / 15.0)  # Expect at least 15 fields for full score
        
        # Weighted average
        confidence = (
            source_quality * 0.3 +
            field_coverage * 0.3 +
            common_field_score * 0.2 +
            completeness_score * 0.2
        )
        
        return round(confidence, 3)