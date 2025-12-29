"""Anomaly detector for identifying outliers and anomalous data patterns."""

import logging
import re
import statistics
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from ...models.harmonization import EnrichedData
from .statistical_analyzer import StatisticalAnalyzer
from ...models.quality_assurance import (
    Anomaly,
    AnomalyReport,
    AnomalyType,
    SeverityLevel,
)

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Component for detecting anomalies and outliers in data."""
    
    def __init__(self):
        """Initialize the anomaly detector."""
        self.name = "AnomalyDetector"
        
        # Initialize components
        self.statistical_analyzer = StatisticalAnalyzer()
        
        # Fields to analyze for anomalies
        self.analyzable_fields = [
            "compound_name",
            "indication",
            "development_phase",
            "therapeutic_area",
            "mechanism_of_action"
        ]
        
        # Statistical thresholds
        self.outlier_threshold = 2.0  # Standard deviations for outlier detection
        self.rare_value_threshold = 0.05  # 5% threshold for rare values
        
        # Expected patterns for pharmaceutical data
        self.expected_patterns = {
            "development_phase": [
                "preclinical", "phase i", "phase ii", "phase iii", "phase iv",
                "phase 1", "phase 2", "phase 3", "phase 4", "approved", "discontinued"
            ],
            "therapeutic_area": [
                "oncology", "neurology", "cardiology", "immunology", "infectious diseases",
                "endocrinology", "respiratory", "gastroenterology", "dermatology", "ophthalmology"
            ]
        }
        
        logger.debug(f"Initialized {self.name} with {len(self.analyzable_fields)} analyzable fields")
    
    async def detect_anomalies(self, data: List[EnrichedData]) -> AnomalyReport:
        """Detect anomalies and outliers in the dataset.
        
        Args:
            data: List of enriched data entries to analyze
            
        Returns:
            AnomalyReport with detailed anomaly analysis
        """
        logger.info(f"Detecting anomalies in {len(data)} records")
        
        if not data:
            return AnomalyReport(
                total_records_analyzed=0,
                anomalies=[],
                anomalies_by_type={},
                anomalies_by_severity={},
                overall_anomaly_score=0.0,
                statistical_summary={}
            )
        
        anomalies = []
        
        # Detect different types of anomalies
        for field_name in self.analyzable_fields:
            field_anomalies = await self._detect_field_anomalies(data, field_name)
            anomalies.extend(field_anomalies)
        
        # Detect cross-field anomalies
        cross_field_anomalies = await self._detect_cross_field_anomalies(data)
        anomalies.extend(cross_field_anomalies)
        
        # Detect clustering-based anomalies using statistical analyzer
        numeric_fields = ["development_phase_numeric"]  # Add numeric representations if available
        clustering_anomalies = self.statistical_analyzer.detect_clustering_anomalies(data, numeric_fields)
        anomalies.extend(clustering_anomalies)
        
        # Categorize anomalies
        anomalies_by_type = self._categorize_by_type(anomalies)
        anomalies_by_severity = self._categorize_by_severity(anomalies)
        
        # Calculate overall anomaly score
        overall_score = self._calculate_anomaly_score(anomalies, len(data))
        
        # Generate statistical summary
        statistical_summary = self._generate_statistical_summary(data, anomalies)
        
        return AnomalyReport(
            total_records_analyzed=len(data),
            anomalies=anomalies,
            anomalies_by_type=anomalies_by_type,
            anomalies_by_severity=anomalies_by_severity,
            overall_anomaly_score=overall_score,
            statistical_summary=statistical_summary
        )
    
    async def _detect_field_anomalies(
        self, 
        data: List[EnrichedData], 
        field_name: str
    ) -> List[Anomaly]:
        """Detect anomalies for a specific field.
        
        Args:
            data: List of enriched data entries
            field_name: Name of the field to analyze
            
        Returns:
            List of anomalies found for the field
        """
        anomalies = []
        
        # Extract field values
        field_values = []
        value_to_entries = defaultdict(list)
        
        for entry in data:
            value = self._get_field_value(entry, field_name)
            if value is not None:
                field_values.append(value)
                value_to_entries[value].append(entry)
        
        if not field_values:
            return anomalies
        
        # Detect statistical outliers for numeric fields
        if all(isinstance(v, (int, float)) for v in field_values):
            outlier_anomalies = self._detect_statistical_outliers(
                field_values, value_to_entries, field_name
            )
            anomalies.extend(outlier_anomalies)
        
        # Detect format anomalies
        format_anomalies = self._detect_format_anomalies(
            field_values, value_to_entries, field_name
        )
        anomalies.extend(format_anomalies)
        
        # Detect value range anomalies
        range_anomalies = self._detect_value_range_anomalies(
            field_values, value_to_entries, field_name
        )
        anomalies.extend(range_anomalies)
        
        # Detect pattern anomalies
        pattern_anomalies = self._detect_pattern_anomalies(
            field_values, value_to_entries, field_name
        )
        anomalies.extend(pattern_anomalies)
        
        return anomalies
    
    async def _detect_cross_field_anomalies(self, data: List[EnrichedData]) -> List[Anomaly]:
        """Detect anomalies across multiple fields.
        
        Args:
            data: List of enriched data entries
            
        Returns:
            List of cross-field anomalies
        """
        anomalies = []
        
        # Check for logical inconsistencies
        for entry in data:
            # Check phase progression logic
            phase_anomaly = self._check_phase_progression_anomaly(entry)
            if phase_anomaly:
                anomalies.append(phase_anomaly)
            
            # Check therapeutic area and indication consistency
            therapeutic_anomaly = self._check_therapeutic_consistency_anomaly(entry)
            if therapeutic_anomaly:
                anomalies.append(therapeutic_anomaly)
        
        return anomalies
    
    def _detect_statistical_outliers(
        self, 
        values: List[Any], 
        value_to_entries: Dict[Any, List[EnrichedData]], 
        field_name: str
    ) -> List[Anomaly]:
        """Detect statistical outliers in numeric data.
        
        Args:
            values: List of field values
            value_to_entries: Mapping of values to entries
            field_name: Name of the field
            
        Returns:
            List of statistical outlier anomalies
        """
        anomalies = []
        
        if len(values) < 3:  # Need at least 3 values for meaningful statistics
            return anomalies
        
        try:
            mean_val = statistics.mean(values)
            stdev_val = statistics.stdev(values)
            
            if stdev_val == 0:  # All values are the same
                return anomalies
            
            for value in set(values):
                z_score = abs((value - mean_val) / stdev_val)
                
                if z_score > self.outlier_threshold:
                    # This is a statistical outlier
                    for entry in value_to_entries[value]:
                        anomaly = Anomaly(
                            anomaly_type=AnomalyType.STATISTICAL_OUTLIER,
                            field_name=field_name,
                            record_id=entry.id,
                            anomalous_value=value,
                            expected_range=f"Mean: {mean_val:.2f} ± {stdev_val:.2f}",
                            confidence_score=min(1.0, z_score / 3.0),  # Normalize to 0-1
                            severity=SeverityLevel.HIGH if z_score > 3.0 else SeverityLevel.MEDIUM,
                            description=f"Statistical outlier: value {value} is {z_score:.1f} standard deviations from mean",
                            context={"z_score": z_score, "mean": mean_val, "stdev": stdev_val}
                        )
                        anomalies.append(anomaly)
        
        except (statistics.StatisticsError, ValueError) as e:
            logger.debug(f"Could not calculate statistics for {field_name}: {e}")
        
        return anomalies
    
    def _detect_format_anomalies(
        self, 
        values: List[Any], 
        value_to_entries: Dict[Any, List[EnrichedData]], 
        field_name: str
    ) -> List[Anomaly]:
        """Detect format anomalies in data.
        
        Args:
            values: List of field values
            value_to_entries: Mapping of values to entries
            field_name: Name of the field
            
        Returns:
            List of format anomalies
        """
        anomalies = []
        
        # Convert all values to strings for format analysis
        string_values = [str(v) for v in values if v is not None]
        
        if not string_values:
            return anomalies
        
        # Detect common format patterns
        format_patterns = defaultdict(list)
        
        for value in string_values:
            # Categorize by format patterns
            if re.match(r'^\d+$', value):
                format_patterns['numeric'].append(value)
            elif re.match(r'^[A-Za-z\s]+$', value):
                format_patterns['alphabetic'].append(value)
            elif re.match(r'^[A-Za-z0-9\s\-]+$', value):
                format_patterns['alphanumeric'].append(value)
            elif re.match(r'.*[^\w\s\-].*', value):
                format_patterns['special_chars'].append(value)
            else:
                format_patterns['other'].append(value)
        
        # Find minority formats (potential anomalies)
        total_values = len(string_values)
        
        for format_type, format_values in format_patterns.items():
            format_ratio = len(format_values) / total_values
            
            # If this format is rare (less than 10% of values), flag as anomaly
            if format_ratio < 0.1 and len(format_values) < 3:
                for value in format_values:
                    original_value = next(v for v in values if str(v) == value)
                    for entry in value_to_entries[original_value]:
                        anomaly = Anomaly(
                            anomaly_type=AnomalyType.FORMAT_ANOMALY,
                            field_name=field_name,
                            record_id=entry.id,
                            anomalous_value=original_value,
                            confidence_score=1.0 - format_ratio,
                            severity=SeverityLevel.LOW,
                            description=f"Unusual format: {format_type} format is rare in this field",
                            context={"format_type": format_type, "format_ratio": format_ratio}
                        )
                        anomalies.append(anomaly)
        
        return anomalies
    
    def _detect_value_range_anomalies(
        self, 
        values: List[Any], 
        value_to_entries: Dict[Any, List[EnrichedData]], 
        field_name: str
    ) -> List[Anomaly]:
        """Detect value range anomalies.
        
        Args:
            values: List of field values
            value_to_entries: Mapping of values to entries
            field_name: Name of the field
            
        Returns:
            List of value range anomalies
        """
        anomalies = []
        
        # Check for extremely long or short text values
        if all(isinstance(v, str) for v in values):
            lengths = [len(v) for v in values]
            
            if len(lengths) > 2:
                try:
                    mean_length = statistics.mean(lengths)
                    stdev_length = statistics.stdev(lengths)
                    
                    for value in values:
                        length = len(value)
                        if stdev_length > 0:
                            z_score = abs((length - mean_length) / stdev_length)
                            
                            if z_score > 2.0:  # Unusual length
                                for entry in value_to_entries[value]:
                                    severity = SeverityLevel.HIGH if z_score > 3.0 else SeverityLevel.MEDIUM
                                    anomaly = Anomaly(
                                        anomaly_type=AnomalyType.VALUE_RANGE_ANOMALY,
                                        field_name=field_name,
                                        record_id=entry.id,
                                        anomalous_value=value,
                                        expected_range=f"Typical length: {mean_length:.0f} ± {stdev_length:.0f} characters",
                                        confidence_score=min(1.0, z_score / 3.0),
                                        severity=severity,
                                        description=f"Unusual text length: {length} characters (z-score: {z_score:.1f})",
                                        context={"length": length, "z_score": z_score}
                                    )
                                    anomalies.append(anomaly)
                
                except statistics.StatisticsError:
                    pass
        
        return anomalies
    
    def _detect_pattern_anomalies(
        self, 
        values: List[Any], 
        value_to_entries: Dict[Any, List[EnrichedData]], 
        field_name: str
    ) -> List[Anomaly]:
        """Detect pattern anomalies based on expected patterns.
        
        Args:
            values: List of field values
            value_to_entries: Mapping of values to entries
            field_name: Name of the field
            
        Returns:
            List of pattern anomalies
        """
        anomalies = []
        
        # Check against expected patterns for this field
        if field_name not in self.expected_patterns:
            return anomalies
        
        expected_values = self.expected_patterns[field_name]
        
        for value in values:
            if isinstance(value, str):
                normalized_value = value.lower().strip()
                
                # Check if value matches any expected pattern
                matches_pattern = any(
                    expected.lower() in normalized_value or normalized_value in expected.lower()
                    for expected in expected_values
                )
                
                if not matches_pattern:
                    # This value doesn't match expected patterns
                    for entry in value_to_entries[value]:
                        anomaly = Anomaly(
                            anomaly_type=AnomalyType.PATTERN_ANOMALY,
                            field_name=field_name,
                            record_id=entry.id,
                            anomalous_value=value,
                            expected_range=f"Expected values: {', '.join(expected_values[:5])}...",
                            confidence_score=0.7,
                            severity=SeverityLevel.MEDIUM,
                            description=f"Value doesn't match expected patterns for {field_name}",
                            context={"expected_patterns": expected_values}
                        )
                        anomalies.append(anomaly)
        
        return anomalies
    
    def _check_phase_progression_anomaly(self, entry: EnrichedData) -> Optional[Anomaly]:
        """Check for phase progression anomalies.
        
        Args:
            entry: EnrichedData entry to check
            
        Returns:
            Anomaly if found, None otherwise
        """
        phase = self._get_field_value(entry, "development_phase")
        
        if not phase or not isinstance(phase, str):
            return None
        
        phase_lower = phase.lower().strip()
        
        # Check for impossible phase combinations or progressions
        impossible_patterns = [
            "phase iv preclinical",
            "approved phase i",
            "discontinued approved"
        ]
        
        for pattern in impossible_patterns:
            if pattern in phase_lower:
                return Anomaly(
                    anomaly_type=AnomalyType.PATTERN_ANOMALY,
                    field_name="development_phase",
                    record_id=entry.id,
                    anomalous_value=phase,
                    confidence_score=0.9,
                    severity=SeverityLevel.HIGH,
                    description=f"Impossible phase progression or combination: {phase}",
                    context={"pattern_matched": pattern}
                )
        
        return None
    
    def _check_therapeutic_consistency_anomaly(self, entry: EnrichedData) -> Optional[Anomaly]:
        """Check for therapeutic area and indication consistency anomalies.
        
        Args:
            entry: EnrichedData entry to check
            
        Returns:
            Anomaly if found, None otherwise
        """
        therapeutic_area = self._get_field_value(entry, "therapeutic_area")
        indication = self._get_field_value(entry, "indication")
        
        if not therapeutic_area or not indication:
            return None
        
        # Simple consistency checks (this could be expanded with more domain knowledge)
        therapeutic_lower = str(therapeutic_area).lower()
        indication_lower = str(indication).lower()
        
        # Check for obvious mismatches
        mismatches = [
            ("oncology", ["diabetes", "hypertension", "depression"]),
            ("cardiology", ["cancer", "tumor", "leukemia"]),
            ("neurology", ["heart", "cardiac", "cardiovascular"])
        ]
        
        for area, conflicting_terms in mismatches:
            if area in therapeutic_lower:
                for term in conflicting_terms:
                    if term in indication_lower:
                        return Anomaly(
                            anomaly_type=AnomalyType.PATTERN_ANOMALY,
                            field_name="therapeutic_area",
                            record_id=entry.id,
                            anomalous_value=therapeutic_area,
                            confidence_score=0.8,
                            severity=SeverityLevel.MEDIUM,
                            description=f"Potential mismatch between therapeutic area '{therapeutic_area}' and indication '{indication}'",
                            context={"indication": indication, "conflicting_term": term}
                        )
        
        return None
    
    def _get_field_value(self, entry: EnrichedData, field_name: str) -> Any:
        """Get field value from enriched data entry."""
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
        
        return None
    
    def _categorize_by_type(self, anomalies: List[Anomaly]) -> Dict[AnomalyType, int]:
        """Categorize anomalies by type."""
        return dict(Counter(anomaly.anomaly_type for anomaly in anomalies))
    
    def _categorize_by_severity(self, anomalies: List[Anomaly]) -> Dict[SeverityLevel, int]:
        """Categorize anomalies by severity."""
        return dict(Counter(anomaly.severity for anomaly in anomalies))
    
    def _calculate_anomaly_score(self, anomalies: List[Anomaly], total_records: int) -> float:
        """Calculate overall anomaly score (0.0 = no anomalies, 1.0 = many anomalies)."""
        if total_records == 0:
            return 0.0
        
        # Weight anomalies by severity
        severity_weights = {
            SeverityLevel.CRITICAL: 1.0,
            SeverityLevel.HIGH: 0.8,
            SeverityLevel.MEDIUM: 0.5,
            SeverityLevel.LOW: 0.2,
            SeverityLevel.INFO: 0.1
        }
        
        weighted_anomalies = sum(
            severity_weights.get(anomaly.severity, 0.5) 
            for anomaly in anomalies
        )
        
        # Normalize by total records
        score = min(1.0, weighted_anomalies / total_records)
        return score
    
    def _generate_statistical_summary(
        self, 
        data: List[EnrichedData], 
        anomalies: List[Anomaly]
    ) -> Dict[str, Any]:
        """Generate statistical summary of the analysis."""
        return {
            "total_records": len(data),
            "total_anomalies": len(anomalies),
            "anomaly_rate": len(anomalies) / len(data) if data else 0.0,
            "fields_analyzed": len(self.analyzable_fields),
            "most_common_anomaly_type": max(
                Counter(a.anomaly_type for a in anomalies).items(),
                key=lambda x: x[1]
            )[0].value if anomalies else None,
            "severity_distribution": dict(Counter(a.severity for a in anomalies))
        }