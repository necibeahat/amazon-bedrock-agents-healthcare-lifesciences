"""Completeness checker for data quality assessment."""

import logging
from typing import Any, Dict, List, Set

from ...models.harmonization import EnrichedData
from ...models.quality_assurance import (
    CompletenessReport,
    FieldAssessment,
    QualityDimension,
)

logger = logging.getLogger(__name__)


class CompletenessChecker:
    """Component for assessing data completeness."""
    
    def __init__(self):
        """Initialize the completeness checker."""
        self.name = "CompletenessChecker"
        logger.debug(f"Initialized {self.name}")
    
    async def assess_completeness(
        self, 
        data: List[EnrichedData], 
        required_fields: List[str]
    ) -> CompletenessReport:
        """Assess completeness of data for required fields.
        
        Args:
            data: List of enriched data entries to assess
            required_fields: List of field names that are required
            
        Returns:
            CompletenessReport with detailed completeness assessment
        """
        logger.info(f"Assessing completeness for {len(data)} records with {len(required_fields)} required fields")
        
        if not data:
            return CompletenessReport(
                total_records=0,
                required_fields=required_fields,
                field_assessments=[],
                overall_completeness_score=0.0,
                missing_required_fields=required_fields,
                critical_gaps=required_fields
            )
        
        # Assess each required field
        field_assessments = []
        missing_required_fields = []
        critical_gaps = []
        
        for field_name in required_fields:
            assessment = await self._assess_field_completeness(data, field_name)
            field_assessments.append(assessment)
            
            # Check if field is missing or has critical gaps
            if assessment.valid_records == 0:
                missing_required_fields.append(field_name)
                critical_gaps.append(field_name)
            elif assessment.score < 0.5:  # Less than 50% complete
                critical_gaps.append(field_name)
        
        # Calculate overall completeness score
        overall_score = self._calculate_overall_completeness_score(field_assessments)
        
        return CompletenessReport(
            total_records=len(data),
            required_fields=required_fields,
            field_assessments=field_assessments,
            overall_completeness_score=overall_score,
            missing_required_fields=missing_required_fields,
            critical_gaps=critical_gaps
        )
    
    async def _assess_field_completeness(
        self, 
        data: List[EnrichedData], 
        field_name: str
    ) -> FieldAssessment:
        """Assess completeness for a specific field.
        
        Args:
            data: List of enriched data entries
            field_name: Name of the field to assess
            
        Returns:
            FieldAssessment for the specified field
        """
        total_records = len(data)
        valid_records = 0
        null_records = 0
        issues = []
        sample_invalid_values = []
        
        for entry in data:
            # Check in unified_data first, then original_data
            value = self._get_field_value(entry, field_name)
            
            if self._is_valid_value(value):
                valid_records += 1
            else:
                null_records += 1
                if len(sample_invalid_values) < 10:
                    sample_invalid_values.append(value)
        
        # Calculate completeness score
        score = valid_records / total_records if total_records > 0 else 0.0
        
        # Identify issues
        if null_records > 0:
            null_percentage = (null_records / total_records) * 100
            issues.append(f"{null_percentage:.1f}% of records have null/empty values")
        
        if score < 0.8:
            issues.append(f"Low completeness score: {score:.1%}")
        
        if score == 0.0:
            issues.append("Field is completely missing from all records")
        
        return FieldAssessment(
            field_name=field_name,
            dimension=QualityDimension.COMPLETENESS,
            score=score,
            total_records=total_records,
            valid_records=valid_records,
            null_records=null_records,
            issues=issues,
            sample_invalid_values=sample_invalid_values
        )
    
    def _get_field_value(self, entry: EnrichedData, field_name: str) -> Any:
        """Get field value from enriched data entry.
        
        Args:
            entry: EnrichedData entry
            field_name: Name of the field to retrieve
            
        Returns:
            Field value or None if not found
        """
        # Try unified_data first
        if field_name in entry.unified_data:
            return entry.unified_data[field_name]
        
        # Try nested fields in unified_data
        for key, value in entry.unified_data.items():
            if isinstance(value, dict) and field_name in value:
                return value[field_name]
        
        # Try original_data as fallback
        if field_name in entry.original_data:
            return entry.original_data[field_name]
        
        # Try nested fields in original_data
        for key, value in entry.original_data.items():
            if isinstance(value, dict) and field_name in value:
                return value[field_name]
        
        return None
    
    def _is_valid_value(self, value: Any) -> bool:
        """Check if a value is considered valid (not null/empty).
        
        Args:
            value: Value to check
            
        Returns:
            True if value is valid, False otherwise
        """
        if value is None:
            return False
        
        if isinstance(value, str):
            return len(value.strip()) > 0
        
        if isinstance(value, (list, dict)):
            return len(value) > 0
        
        if isinstance(value, (int, float)):
            return True  # Numbers are always valid unless None
        
        if isinstance(value, bool):
            return True  # Booleans are always valid
        
        # For other types, check if they have a meaningful string representation
        return str(value).strip() != ""
    
    def _calculate_overall_completeness_score(
        self, 
        field_assessments: List[FieldAssessment]
    ) -> float:
        """Calculate overall completeness score from field assessments.
        
        Args:
            field_assessments: List of field assessments
            
        Returns:
            Overall completeness score (0.0 to 1.0)
        """
        if not field_assessments:
            return 0.0
        
        # Simple average of field completeness scores
        total_score = sum(assessment.score for assessment in field_assessments)
        return total_score / len(field_assessments)