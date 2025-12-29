"""Statistical analyzer for advanced data quality metrics and analysis."""

import logging
import statistics
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

from ...models.harmonization import EnrichedData
from ...models.quality_assurance import (
    Anomaly,
    AnomalyType,
    SeverityLevel,
)

logger = logging.getLogger(__name__)


class StatisticalAnalyzer:
    """Advanced statistical analyzer for data quality assessment."""
    
    def __init__(self):
        """Initialize the statistical analyzer."""
        self.name = "StatisticalAnalyzer"
        
        # Statistical thresholds
        self.outlier_z_threshold = 2.5
        self.outlier_iqr_multiplier = 1.5
        self.rare_value_threshold = 0.05  # 5%
        
        logger.debug(f"Initialized {self.name}")
    
    def analyze_numeric_distribution(
        self, 
        values: List[float], 
        field_name: str
    ) -> Dict[str, Any]:
        """Analyze the statistical distribution of numeric values.
        
        Args:
            values: List of numeric values
            field_name: Name of the field being analyzed
            
        Returns:
            Dictionary with statistical analysis results
        """
        if not values or len(values) < 2:
            return {"error": "Insufficient data for statistical analysis"}
        
        try:
            # Basic statistics
            mean_val = statistics.mean(values)
            median_val = statistics.median(values)
            mode_val = statistics.mode(values) if len(set(values)) < len(values) else None
            stdev_val = statistics.stdev(values) if len(values) > 1 else 0
            variance_val = statistics.variance(values) if len(values) > 1 else 0
            
            # Quartiles and IQR (simplified calculation)
            sorted_values = sorted(values)
            n = len(sorted_values)
            q1_idx = n // 4
            q3_idx = 3 * n // 4
            q1 = sorted_values[q1_idx] if q1_idx < n else sorted_values[0]
            q3 = sorted_values[q3_idx] if q3_idx < n else sorted_values[-1]
            iqr = q3 - q1
            
            # Outlier bounds
            lower_bound = q1 - (self.outlier_iqr_multiplier * iqr)
            upper_bound = q3 + (self.outlier_iqr_multiplier * iqr)
            
            return {
                "field_name": field_name,
                "count": len(values),
                "mean": mean_val,
                "median": median_val,
                "mode": mode_val,
                "std_dev": stdev_val,
                "variance": variance_val,
                "min": min(values),
                "max": max(values),
                "range": max(values) - min(values),
                "q1": q1,
                "q3": q3,
                "iqr": iqr,
                "outlier_bounds": {"lower": lower_bound, "upper": upper_bound},
                "coefficient_of_variation": stdev_val / mean_val if mean_val != 0 else None
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze numeric distribution for {field_name}: {e}")
            return {"error": str(e)}
    
    def detect_statistical_outliers(
        self, 
        values: List[float], 
        method: str = "iqr"
    ) -> List[Tuple[int, float, float]]:
        """Detect statistical outliers using various methods.
        
        Args:
            values: List of numeric values
            method: Method to use ("iqr", "z_score", "modified_z_score")
            
        Returns:
            List of tuples (index, value, outlier_score)
        """
        if not values or len(values) < 3:
            return []
        
        outliers = []
        
        try:
            if method == "iqr":
                outliers = self._detect_iqr_outliers(values)
            elif method == "z_score":
                outliers = self._detect_z_score_outliers(values)
            elif method == "modified_z_score":
                outliers = self._detect_modified_z_score_outliers(values)
            else:
                logger.warning(f"Unknown outlier detection method: {method}")
                
        except Exception as e:
            logger.error(f"Failed to detect outliers using {method}: {e}")
        
        return outliers
    
    def _detect_iqr_outliers(self, values: List[float]) -> List[Tuple[int, float, float]]:
        """Detect outliers using Interquartile Range method."""
        sorted_values = sorted(values)
        n = len(sorted_values)
        q1_idx = n // 4
        q3_idx = 3 * n // 4
        q1 = sorted_values[q1_idx] if q1_idx < n else sorted_values[0]
        q3 = sorted_values[q3_idx] if q3_idx < n else sorted_values[-1]
        iqr = q3 - q1
        
        lower_bound = q1 - (self.outlier_iqr_multiplier * iqr)
        upper_bound = q3 + (self.outlier_iqr_multiplier * iqr)
        
        outliers = []
        for i, value in enumerate(values):
            if value < lower_bound or value > upper_bound:
                # Calculate outlier score (distance from nearest bound)
                if value < lower_bound:
                    score = (lower_bound - value) / iqr if iqr > 0 else 1.0
                else:
                    score = (value - upper_bound) / iqr if iqr > 0 else 1.0
                outliers.append((i, value, score))
        
        return outliers
    
    def _detect_z_score_outliers(self, values: List[float]) -> List[Tuple[int, float, float]]:
        """Detect outliers using Z-score method."""
        if len(values) < 2:
            return []
        
        mean_val = statistics.mean(values)
        stdev_val = statistics.stdev(values)
        
        if stdev_val == 0:
            return []
        
        outliers = []
        for i, value in enumerate(values):
            z_score = abs((value - mean_val) / stdev_val)
            if z_score > self.outlier_z_threshold:
                outliers.append((i, value, z_score))
        
        return outliers
    
    def _detect_modified_z_score_outliers(self, values: List[float]) -> List[Tuple[int, float, float]]:
        """Detect outliers using Modified Z-score method (more robust)."""
        median_val = statistics.median(values)
        mad = statistics.median([abs(x - median_val) for x in values])
        
        if mad == 0:
            return []
        
        outliers = []
        for i, value in enumerate(values):
            modified_z_score = 0.6745 * (value - median_val) / mad
            if abs(modified_z_score) > self.outlier_z_threshold:
                outliers.append((i, value, abs(modified_z_score)))
        
        return outliers
    
    def analyze_categorical_distribution(
        self, 
        values: List[str], 
        field_name: str
    ) -> Dict[str, Any]:
        """Analyze the distribution of categorical values.
        
        Args:
            values: List of categorical values
            field_name: Name of the field being analyzed
            
        Returns:
            Dictionary with categorical analysis results
        """
        if not values:
            return {"error": "No data for categorical analysis"}
        
        try:
            # Value counts and frequencies
            value_counts = Counter(values)
            total_count = len(values)
            
            # Calculate frequencies
            value_frequencies = {
                value: count / total_count 
                for value, count in value_counts.items()
            }
            
            # Identify rare values
            rare_values = {
                value: freq 
                for value, freq in value_frequencies.items() 
                if freq < self.rare_value_threshold
            }
            
            # Calculate entropy (measure of diversity) - simplified
            entropy = 0.0
            for freq in value_frequencies.values():
                if freq > 0:
                    # Using natural log instead of log2 for simplicity
                    import math
                    entropy -= freq * math.log(freq)
            
            # Gini impurity
            gini_impurity = 1 - sum(freq ** 2 for freq in value_frequencies.values())
            
            return {
                "field_name": field_name,
                "total_count": total_count,
                "unique_values": len(value_counts),
                "value_counts": dict(value_counts.most_common()),
                "value_frequencies": value_frequencies,
                "rare_values": rare_values,
                "most_common": value_counts.most_common(1)[0] if value_counts else None,
                "entropy": entropy,
                "gini_impurity": gini_impurity,
                "diversity_ratio": len(value_counts) / total_count
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze categorical distribution for {field_name}: {e}")
            return {"error": str(e)}
    
    def detect_clustering_anomalies(
        self, 
        data: List[EnrichedData], 
        numeric_fields: List[str]
    ) -> List[Anomaly]:
        """Detect anomalies using simplified clustering analysis.
        
        Args:
            data: List of enriched data entries
            numeric_fields: List of numeric fields to use for clustering
            
        Returns:
            List of clustering-based anomalies
        """
        if not data or not numeric_fields:
            return []
        
        try:
            # Extract numeric features (simplified approach)
            features = []
            valid_entries = []
            
            for entry in data:
                feature_vector = []
                is_valid = True
                
                for field_name in numeric_fields:
                    value = self._get_numeric_field_value(entry, field_name)
                    if value is not None:
                        feature_vector.append(float(value))
                    else:
                        is_valid = False
                        break
                
                if is_valid and feature_vector:
                    features.append(feature_vector)
                    valid_entries.append(entry)
            
            if len(features) < 3:
                return []
            
            # Simplified outlier detection based on distance from mean
            anomalies = []
            
            # Calculate mean for each dimension
            if features:
                num_dimensions = len(features[0])
                means = []
                stdevs = []
                
                for dim in range(num_dimensions):
                    dim_values = [feature[dim] for feature in features]
                    means.append(statistics.mean(dim_values))
                    stdevs.append(statistics.stdev(dim_values) if len(dim_values) > 1 else 1.0)
                
                # Find outliers based on standardized distance
                for i, (entry, feature_vector) in enumerate(zip(valid_entries, features)):
                    # Calculate standardized distance from mean
                    distances = []
                    for dim in range(num_dimensions):
                        if stdevs[dim] > 0:
                            standardized_distance = abs((feature_vector[dim] - means[dim]) / stdevs[dim])
                            distances.append(standardized_distance)
                    
                    if distances:
                        max_distance = max(distances)
                        if max_distance > 2.0:  # Outlier threshold
                            anomaly = Anomaly(
                                anomaly_type=AnomalyType.STATISTICAL_OUTLIER,
                                field_name="multi_field_clustering",
                                record_id=entry.id,
                                anomalous_value=f"Outlier in {len(numeric_fields)}-dimensional space",
                                confidence_score=min(1.0, max_distance / 3.0),
                                severity=SeverityLevel.HIGH if max_distance > 3.0 else SeverityLevel.MEDIUM,
                                description=f"Record is an outlier in {len(numeric_fields)}-dimensional analysis",
                                context={
                                    "clustering_method": "simplified_distance",
                                    "fields_analyzed": numeric_fields,
                                    "max_standardized_distance": max_distance
                                }
                            )
                            anomalies.append(anomaly)
            
            return anomalies
            
        except Exception as e:
            logger.error(f"Failed to detect clustering anomalies: {e}")
            return []
    
    def _get_numeric_field_value(self, entry: EnrichedData, field_name: str) -> Optional[float]:
        """Get numeric field value from enriched data entry."""
        # Try unified_data first
        if field_name in entry.unified_data:
            value = entry.unified_data[field_name]
        else:
            # Try nested fields in unified_data
            value = None
            for key, val in entry.unified_data.items():
                if isinstance(val, dict) and field_name in val:
                    value = val[field_name]
                    break
            
            # Try original_data as fallback
            if value is None and field_name in entry.original_data:
                value = entry.original_data[field_name]
        
        # Convert to float if possible
        if value is not None:
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        
        return None
    
    def calculate_data_quality_score(
        self, 
        completeness_score: float,
        consistency_score: float, 
        anomaly_score: float,
        accuracy_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """Calculate overall data quality score with statistical confidence.
        
        Args:
            completeness_score: Completeness score (0-1)
            consistency_score: Consistency score (0-1)
            anomaly_score: Anomaly score (0-1, lower is better)
            accuracy_score: Optional accuracy score (0-1)
            
        Returns:
            Dictionary with quality score and confidence metrics
        """
        # Weights for different quality dimensions
        weights = {
            "completeness": 0.3,
            "consistency": 0.3,
            "normality": 0.2,  # Inverse of anomaly score
            "accuracy": 0.2
        }
        
        # Calculate weighted score
        scores = {
            "completeness": completeness_score,
            "consistency": consistency_score,
            "normality": 1.0 - anomaly_score,  # Invert anomaly score
        }
        
        if accuracy_score is not None:
            scores["accuracy"] = accuracy_score
        else:
            # Redistribute accuracy weight to other dimensions
            weights["completeness"] += weights["accuracy"] * 0.4
            weights["consistency"] += weights["accuracy"] * 0.4
            weights["normality"] += weights["accuracy"] * 0.2
            del weights["accuracy"]
        
        # Calculate weighted average
        weighted_sum = sum(scores[dim] * weights[dim] for dim in scores)
        total_weight = sum(weights.values())
        
        overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        # Calculate confidence based on score variance
        score_values = list(scores.values())
        score_variance = statistics.variance(score_values) if len(score_values) > 1 else 0.0
        confidence = max(0.5, 1.0 - score_variance)  # Higher variance = lower confidence
        
        # Determine quality grade
        if overall_score >= 0.9:
            grade = "A"
        elif overall_score >= 0.8:
            grade = "B"
        elif overall_score >= 0.7:
            grade = "C"
        elif overall_score >= 0.6:
            grade = "D"
        else:
            grade = "F"
        
        return {
            "overall_score": overall_score,
            "quality_grade": grade,
            "confidence": confidence,
            "dimension_scores": scores,
            "dimension_weights": weights,
            "score_variance": score_variance
        }