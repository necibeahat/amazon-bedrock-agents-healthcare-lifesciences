"""Consistency validator for cross-source data validation."""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple

from ...models.harmonization import EnrichedData
from ...models.quality_assurance import (
    ConsistencyIssue,
    ConsistencyReport,
    SeverityLevel,
)

logger = logging.getLogger(__name__)


class ConsistencyValidator:
    """Component for validating data consistency across sources."""
    
    def __init__(self):
        """Initialize the consistency validator."""
        self.name = "ConsistencyValidator"
        
        # Fields that should be consistent across sources for the same entity
        self.consistency_fields = [
            "compound_name",
            "indication",
            "development_phase",
            "therapeutic_area",
            "mechanism_of_action"
        ]
        
        # Tolerance for numeric comparisons
        self.numeric_tolerance = 0.01
        
        logger.debug(f"Initialized {self.name} with {len(self.consistency_fields)} consistency fields")
    
    async def validate_consistency(self, data: List[EnrichedData]) -> ConsistencyReport:
        """Validate consistency of data across sources.
        
        Args:
            data: List of enriched data entries to validate
            
        Returns:
            ConsistencyReport with detailed consistency analysis
        """
        logger.info(f"Validating consistency for {len(data)} records")
        
        if not data:
            return ConsistencyReport(
                total_records=0,
                cross_source_checks=0,
                consistency_issues=[],
                overall_consistency_score=1.0,
                sources_compared=[],
                field_consistency_scores={}
            )
        
        # Group data by potential duplicates (same compound and indication)
        entity_groups = self._group_potential_duplicates(data)
        
        # Find consistency issues
        consistency_issues = []
        field_consistency_scores = {}
        total_checks = 0
        
        for field_name in self.consistency_fields:
            field_issues, field_checks = await self._validate_field_consistency(
                entity_groups, field_name
            )
            consistency_issues.extend(field_issues)
            total_checks += field_checks
            
            # Calculate field consistency score
            field_score = 1.0 - (len(field_issues) / max(field_checks, 1))
            field_consistency_scores[field_name] = field_score
        
        # Get list of sources compared
        sources_compared = list(set(
            self._get_source_company(entry) for entry in data
            if self._get_source_company(entry)
        ))
        
        # Calculate overall consistency score
        overall_score = self._calculate_overall_consistency_score(
            consistency_issues, total_checks
        )
        
        return ConsistencyReport(
            total_records=len(data),
            cross_source_checks=total_checks,
            consistency_issues=consistency_issues,
            overall_consistency_score=overall_score,
            sources_compared=sources_compared,
            field_consistency_scores=field_consistency_scores
        )
    
    def _group_potential_duplicates(
        self, 
        data: List[EnrichedData]
    ) -> Dict[str, List[EnrichedData]]:
        """Group data entries that might represent the same entity.
        
        Args:
            data: List of enriched data entries
            
        Returns:
            Dictionary mapping entity keys to lists of potentially duplicate entries
        """
        groups = defaultdict(list)
        
        for entry in data:
            # Create a key based on compound name and primary indication
            compound_name = self._get_field_value(entry, "compound_name")
            indication = self._get_field_value(entry, "indication")
            
            if compound_name and indication:
                # Normalize for grouping
                key = f"{self._normalize_text(compound_name)}|{self._normalize_text(indication)}"
                groups[key].append(entry)
        
        # Only return groups with multiple entries (potential duplicates)
        return {key: entries for key, entries in groups.items() if len(entries) > 1}
    
    async def _validate_field_consistency(
        self, 
        entity_groups: Dict[str, List[EnrichedData]], 
        field_name: str
    ) -> Tuple[List[ConsistencyIssue], int]:
        """Validate consistency for a specific field across entity groups.
        
        Args:
            entity_groups: Groups of potentially duplicate entities
            field_name: Name of the field to validate
            
        Returns:
            Tuple of (consistency issues found, total checks performed)
        """
        issues = []
        total_checks = 0
        
        for entity_key, entries in entity_groups.items():
            if len(entries) < 2:
                continue
            
            # Get all values for this field across entries
            field_values = []
            entry_sources = []
            
            for entry in entries:
                value = self._get_field_value(entry, field_name)
                source = self._get_source_company(entry)
                
                if value is not None:
                    field_values.append(value)
                    entry_sources.append((entry.id, source, value))
            
            if len(field_values) < 2:
                continue
            
            total_checks += 1
            
            # Check for inconsistencies
            if not self._are_values_consistent(field_values):
                # Create consistency issue
                unique_values = list(set(str(v) for v in field_values))
                affected_records = [entry_id for entry_id, _, _ in entry_sources]
                
                severity = self._determine_severity(field_name, unique_values)
                
                issue = ConsistencyIssue(
                    issue_type="cross_source_inconsistency",
                    field_name=field_name,
                    conflicting_values=unique_values,
                    affected_records=affected_records,
                    severity=severity,
                    description=f"Field '{field_name}' has inconsistent values across sources: {', '.join(unique_values[:3])}"
                )
                issues.append(issue)
        
        return issues, total_checks
    
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
    
    def _get_source_company(self, entry: EnrichedData) -> str:
        """Get source company from enriched data entry.
        
        Args:
            entry: EnrichedData entry
            
        Returns:
            Source company name or empty string
        """
        # Try to get from enrichment metadata
        if "source_company" in entry.enrichment_metadata:
            return entry.enrichment_metadata["source_company"]
        
        # Try to get from unified data
        company_value = self._get_field_value(entry, "company")
        if company_value:
            return str(company_value)
        
        return ""
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        if not isinstance(text, str):
            text = str(text)
        
        return text.lower().strip().replace(" ", "").replace("-", "").replace("_", "")
    
    def _are_values_consistent(self, values: List[Any]) -> bool:
        """Check if a list of values are consistent.
        
        Args:
            values: List of values to check
            
        Returns:
            True if values are consistent, False otherwise
        """
        if len(values) <= 1:
            return True
        
        # For numeric values, use tolerance-based comparison
        if all(isinstance(v, (int, float)) for v in values):
            min_val = min(values)
            max_val = max(values)
            return (max_val - min_val) <= self.numeric_tolerance
        
        # For text values, normalize and compare
        if all(isinstance(v, str) for v in values):
            normalized_values = [self._normalize_text(v) for v in values]
            return len(set(normalized_values)) == 1
        
        # For other types, convert to string and compare
        string_values = [str(v).strip().lower() for v in values]
        return len(set(string_values)) == 1
    
    def _determine_severity(self, field_name: str, conflicting_values: List[str]) -> SeverityLevel:
        """Determine severity level for a consistency issue.
        
        Args:
            field_name: Name of the field with inconsistency
            conflicting_values: List of conflicting values
            
        Returns:
            SeverityLevel for the issue
        """
        # Critical fields that should always be consistent
        critical_fields = ["compound_name", "indication"]
        
        if field_name in critical_fields:
            return SeverityLevel.CRITICAL
        
        # High importance fields
        high_importance_fields = ["development_phase", "therapeutic_area"]
        
        if field_name in high_importance_fields:
            return SeverityLevel.HIGH
        
        # Check if values are completely different or just minor variations
        if len(conflicting_values) > 3:
            return SeverityLevel.HIGH
        
        # Check if values might be minor variations
        if all(len(v) > 0 for v in conflicting_values):
            # If all values have some similarity, it might be a minor issue
            normalized = [self._normalize_text(v) for v in conflicting_values]
            if any(norm1 in norm2 or norm2 in norm1 for norm1 in normalized for norm2 in normalized if norm1 != norm2):
                return SeverityLevel.MEDIUM
        
        return SeverityLevel.MEDIUM
    
    def _calculate_overall_consistency_score(
        self, 
        consistency_issues: List[ConsistencyIssue], 
        total_checks: int
    ) -> float:
        """Calculate overall consistency score.
        
        Args:
            consistency_issues: List of consistency issues found
            total_checks: Total number of consistency checks performed
            
        Returns:
            Overall consistency score (0.0 to 1.0)
        """
        if total_checks == 0:
            return 1.0  # No checks means perfect consistency
        
        # Weight issues by severity
        severity_weights = {
            SeverityLevel.CRITICAL: 1.0,
            SeverityLevel.HIGH: 0.8,
            SeverityLevel.MEDIUM: 0.5,
            SeverityLevel.LOW: 0.2,
            SeverityLevel.INFO: 0.1
        }
        
        weighted_issues = sum(
            severity_weights.get(issue.severity, 0.5) 
            for issue in consistency_issues
        )
        
        # Calculate score (higher is better)
        score = max(0.0, 1.0 - (weighted_issues / total_checks))
        return score