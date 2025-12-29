"""Quality Assurance Agent implementation using Strands framework."""

import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from strands import Agent

from ...models.harmonization import DeduplicatedData, EnrichedData, UnifiedDataModel
from ...models.quality_assurance import (
    Anomaly,
    AnomalyReport,
    AnomalyType,
    Assessment,
    CompletenessReport,
    ConsistencyReport,
    FieldAssessment,
    QualityDimension,
    QualityIssue,
    QualityMetric,
    QualityReport,
    SeverityLevel,
)
from ...storage.storage_manager import StorageManager
from .accuracy_validator import AccuracyValidator
from .anomaly_detector import AnomalyDetector
from .completeness_checker import CompletenessChecker
from .consistency_validator import ConsistencyValidator
from .issue_manager import IssueManager
from .report_generator import QualityReportGenerator

logger = logging.getLogger(__name__)


class QualityAssuranceAgent:
    """Quality Assurance Agent for comprehensive data quality assessment."""
    
    def __init__(self, storage_manager: Optional[StorageManager] = None, **kwargs):
        """Initialize the Quality Assurance Agent.
        
        Args:
            storage_manager: Storage manager instance for data persistence
            **kwargs: Additional arguments for configuration
        """
        # Set default agent configuration
        self.name = kwargs.get('name', 'QualityAssuranceAgent')
        self.description = kwargs.get('description', 'Performs comprehensive data quality assessment and anomaly detection')
        
        # Initialize quality assessment components
        self.completeness_checker = CompletenessChecker()
        self.consistency_validator = ConsistencyValidator()
        self.accuracy_validator = AccuracyValidator()
        self.anomaly_detector = AnomalyDetector()
        self.report_generator = QualityReportGenerator()
        self.issue_manager = IssueManager()
        self.storage_manager = storage_manager
        
        # Quality thresholds (configurable)
        self.quality_thresholds = {
            QualityDimension.COMPLETENESS: 0.85,
            QualityDimension.CONSISTENCY: 0.90,
            QualityDimension.ACCURACY: 0.80,
            QualityDimension.VALIDITY: 0.85,
            QualityDimension.TIMELINESS: 0.75
        }
        
        # Required fields for pharmaceutical pipeline data
        self.required_fields = [
            "compound_name",
            "indication",
            "development_phase",
            "therapeutic_area",
            "company"
        ]
        
        logger.info(f"Initialized {self.name} with comprehensive quality assessment capabilities")
    
    async def assess_data_quality(self, data: DeduplicatedData, unified_model: UnifiedDataModel) -> Dict:
        """Perform comprehensive quality assessment on unified data.
        
        Args:
            data: Deduplicated unified data to assess
            unified_model: Unified data model for validation context
            
        Returns:
            Dictionary with complete quality assessment results
        """
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting comprehensive quality assessment for {len(data.canonical_entries)} records")
            
            # Perform individual quality assessments
            completeness_report = await self._assess_completeness(data.canonical_entries)
            consistency_report = await self._assess_consistency(data.canonical_entries)
            anomaly_report = await self._detect_anomalies(data.canonical_entries)
            
            # Calculate overall quality metrics
            quality_metrics = self._calculate_quality_metrics(
                completeness_report, consistency_report, anomaly_report
            )
            
            # Create comprehensive assessment
            assessment = Assessment(
                dataset_id=data.id,
                dataset_name=f"Pharmaceutical Pipeline Data - {len(data.canonical_entries)} records",
                total_records=len(data.canonical_entries),
                completeness_report=completeness_report,
                consistency_report=consistency_report,
                anomaly_report=anomaly_report,
                quality_metrics=quality_metrics,
                overall_quality_score=self._calculate_overall_score(quality_metrics),
                critical_issues=self._identify_critical_issues(completeness_report, consistency_report, anomaly_report),
                recommendations=self._generate_recommendations(completeness_report, consistency_report, anomaly_report),
                assessment_duration_seconds=(datetime.utcnow() - start_time).total_seconds()
            )
            
            # Store assessment if storage manager is available
            if self.storage_manager:
                storage_result = await self._store_assessment(assessment)
                assessment.assessment_metadata["storage_result"] = storage_result
            
            return {
                "action": "assess_data_quality",
                "assessment": assessment.model_dump(),
                "summary": {
                    "total_records": len(data.canonical_entries),
                    "overall_quality_score": assessment.overall_quality_score,
                    "critical_issues_count": len(assessment.critical_issues),
                    "recommendations_count": len(assessment.recommendations),
                    "assessment_duration_seconds": assessment.assessment_duration_seconds
                }
            }
            
        except Exception as e:
            error_msg = f"Failed to assess data quality: {e}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    async def assess_completeness(self, data: List[EnrichedData]) -> Dict:
        """Assess data completeness for required fields.
        
        Args:
            data: List of enriched data entries to assess
            
        Returns:
            Dictionary with completeness assessment results
        """
        try:
            logger.info(f"Assessing completeness for {len(data)} records")
            completeness_report = await self._assess_completeness(data)
            
            return {
                "action": "assess_completeness",
                "report": completeness_report.model_dump(),
                "summary": {
                    "overall_score": completeness_report.overall_completeness_score,
                    "critical_gaps": len(completeness_report.critical_gaps),
                    "missing_required_fields": completeness_report.missing_required_fields
                }
            }
            
        except Exception as e:
            error_msg = f"Failed to assess completeness: {e}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    async def validate_consistency(self, data: List[EnrichedData]) -> Dict:
        """Validate data consistency across sources.
        
        Args:
            data: List of enriched data entries to validate
            
        Returns:
            Dictionary with consistency validation results
        """
        try:
            logger.info(f"Validating consistency for {len(data)} records")
            consistency_report = await self._assess_consistency(data)
            
            return {
                "action": "validate_consistency",
                "report": consistency_report.model_dump(),
                "summary": {
                    "overall_score": consistency_report.overall_consistency_score,
                    "issues_count": len(consistency_report.consistency_issues),
                    "sources_compared": consistency_report.sources_compared
                }
            }
            
        except Exception as e:
            error_msg = f"Failed to validate consistency: {e}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    async def detect_anomalies(self, data: List[EnrichedData]) -> Dict:
        """Detect outliers and anomalies in the dataset.
        
        Args:
            data: List of enriched data entries to analyze
            
        Returns:
            Dictionary with anomaly detection results
        """
        try:
            logger.info(f"Detecting anomalies in {len(data)} records")
            anomaly_report = await self._detect_anomalies(data)
            
            return {
                "action": "detect_anomalies",
                "report": anomaly_report.model_dump(),
                "summary": {
                    "total_anomalies": len(anomaly_report.anomalies),
                    "anomaly_score": anomaly_report.overall_anomaly_score,
                    "by_type": anomaly_report.anomalies_by_type,
                    "by_severity": anomaly_report.anomalies_by_severity
                }
            }
            
        except Exception as e:
            error_msg = f"Failed to detect anomalies: {e}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    async def generate_quality_report(
        self, 
        assessments: List[Assessment], 
        report_type: str = "technical"
    ) -> Dict:
        """Generate comprehensive quality report with actionable insights.
        
        Args:
            assessments: List of quality assessments
            report_type: Type of report ("executive", "technical", "operational")
            
        Returns:
            Dictionary with quality report and management actions
        """
        try:
            logger.info(f"Generating {report_type} quality report for {len(assessments)} assessments")
            
            # Generate the quality report
            quality_report = self.report_generator.generate_quality_report(
                assessments, report_type
            )
            
            # Create managed issues for critical problems
            managed_issues = []
            for critical_issue in quality_report.critical_issues:
                managed_issue = self.issue_manager.create_issue(critical_issue)
                managed_issues.append(managed_issue)
            
            # Get issue summary
            issue_summary = self.issue_manager.generate_issue_summary()
            
            # Process any automatic escalations
            escalated_issues = self.issue_manager.process_automatic_escalations()
            
            return {
                "action": "generate_quality_report",
                "report": quality_report.model_dump(),
                "managed_issues_created": len(managed_issues),
                "issue_summary": issue_summary,
                "escalated_issues": escalated_issues,
                "summary": {
                    "report_type": report_type,
                    "overall_quality_score": quality_report.overall_quality_score,
                    "quality_grade": quality_report.quality_grade,
                    "critical_issues_count": len(quality_report.critical_issues),
                    "immediate_actions_count": len(quality_report.immediate_actions),
                    "improvement_recommendations_count": len(quality_report.improvement_recommendations)
                }
            }
            
        except Exception as e:
            error_msg = f"Failed to generate quality report: {e}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    async def flag_critical_issues(self, assessment: Assessment) -> Dict:
        """Flag critical issues requiring human review.
        
        Args:
            assessment: Quality assessment to analyze for critical issues
            
        Returns:
            Dictionary with flagged issues and management actions
        """
        try:
            logger.info(f"Flagging critical issues from assessment {assessment.id}")
            
            # Identify issues requiring human review
            human_review_issues = []
            
            # Check completeness issues
            if assessment.completeness_report:
                for gap in assessment.completeness_report.critical_gaps:
                    if gap in self.required_fields:  # Critical required field
                        human_review_issues.append({
                            "type": "critical_completeness_gap",
                            "field": gap,
                            "severity": "critical",
                            "description": f"Required field '{gap}' has critical completeness issues",
                            "requires_human_review": True
                        })
            
            # Check consistency issues
            if assessment.consistency_report:
                critical_consistency_issues = [
                    issue for issue in assessment.consistency_report.consistency_issues
                    if issue.severity == SeverityLevel.CRITICAL
                ]
                
                for issue in critical_consistency_issues:
                    human_review_issues.append({
                        "type": "critical_consistency_issue",
                        "field": issue.field_name,
                        "severity": "critical",
                        "description": issue.description,
                        "affected_records": len(issue.affected_records),
                        "requires_human_review": True
                    })
            
            # Check critical anomalies
            if assessment.anomaly_report:
                critical_anomalies = [
                    anomaly for anomaly in assessment.anomaly_report.anomalies
                    if anomaly.severity == SeverityLevel.CRITICAL
                ]
                
                for anomaly in critical_anomalies:
                    human_review_issues.append({
                        "type": "critical_anomaly",
                        "field": anomaly.field_name,
                        "severity": "critical",
                        "description": anomaly.description,
                        "confidence_score": anomaly.confidence_score,
                        "requires_human_review": True
                    })
            
            # Create managed issues for human review items
            managed_issues = []
            for issue_data in human_review_issues:
                # Convert to QualityIssue
                quality_issue = QualityIssue(
                    issue_type=issue_data["type"],
                    severity=SeverityLevel.CRITICAL,
                    dimension=QualityDimension.COMPLETENESS if "completeness" in issue_data["type"] else QualityDimension.CONSISTENCY,
                    title=f"Critical Issue: {issue_data['field']}",
                    description=issue_data["description"],
                    requires_human_review=True
                )
                
                managed_issue = self.issue_manager.create_issue(quality_issue)
                managed_issues.append(managed_issue)
            
            return {
                "action": "flag_critical_issues",
                "human_review_issues": human_review_issues,
                "managed_issues_created": len(managed_issues),
                "requires_immediate_attention": len(human_review_issues) > 0,
                "summary": {
                    "total_critical_issues": len(human_review_issues),
                    "completeness_issues": len([i for i in human_review_issues if "completeness" in i["type"]]),
                    "consistency_issues": len([i for i in human_review_issues if "consistency" in i["type"]]),
                    "anomaly_issues": len([i for i in human_review_issues if "anomaly" in i["type"]])
                }
            }
            
        except Exception as e:
            error_msg = f"Failed to flag critical issues: {e}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    async def create_actionable_recommendations(self, assessments: List[Assessment]) -> Dict:
        """Create actionable recommendations for data improvement.
        
        Args:
            assessments: List of quality assessments
            
        Returns:
            Dictionary with categorized recommendations and action plans
        """
        try:
            logger.info(f"Creating actionable recommendations from {len(assessments)} assessments")
            
            if not assessments:
                return {"error": "No assessments provided for recommendations"}
            
            recent_assessment = max(assessments, key=lambda a: a.assessed_at)
            
            recommendations = {
                "immediate_actions": [],
                "short_term_improvements": [],
                "long_term_strategies": [],
                "monitoring_enhancements": []
            }
            
            # Immediate actions based on critical issues
            if recent_assessment.overall_quality_score < 0.5:
                recommendations["immediate_actions"].extend([
                    "Halt data processing until critical quality issues are resolved",
                    "Conduct emergency data quality review meeting",
                    "Implement immediate data validation checks"
                ])
            
            # Completeness-based recommendations
            if recent_assessment.completeness_report:
                completeness_score = recent_assessment.completeness_report.overall_completeness_score
                
                if completeness_score < 0.7:
                    recommendations["immediate_actions"].append(
                        "Implement data collection improvements for missing required fields"
                    )
                    recommendations["short_term_improvements"].append(
                        "Establish data quality SLAs with source systems"
                    )
                
                if recent_assessment.completeness_report.missing_required_fields:
                    for field in recent_assessment.completeness_report.missing_required_fields[:3]:
                        recommendations["immediate_actions"].append(
                            f"Address missing data for required field: {field}"
                        )
            
            # Consistency-based recommendations
            if recent_assessment.consistency_report:
                consistency_score = recent_assessment.consistency_report.overall_consistency_score
                
                if consistency_score < 0.8:
                    recommendations["short_term_improvements"].extend([
                        "Standardize data formats across all sources",
                        "Implement cross-source data validation rules",
                        "Create comprehensive data mapping documentation"
                    ])
                
                high_severity_issues = [
                    issue for issue in recent_assessment.consistency_report.consistency_issues
                    if issue.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]
                ]
                
                if high_severity_issues:
                    recommendations["immediate_actions"].append(
                        f"Resolve {len(high_severity_issues)} high-severity consistency issues"
                    )
            
            # Anomaly-based recommendations
            if recent_assessment.anomaly_report:
                anomaly_score = recent_assessment.anomaly_report.overall_anomaly_score
                
                if anomaly_score > 0.2:
                    recommendations["short_term_improvements"].extend([
                        "Implement automated anomaly detection and alerting",
                        "Establish data profiling and monitoring dashboards",
                        "Create anomaly investigation procedures"
                    ])
                
                critical_anomalies = [
                    anomaly for anomaly in recent_assessment.anomaly_report.anomalies
                    if anomaly.severity == SeverityLevel.CRITICAL
                ]
                
                if critical_anomalies:
                    recommendations["immediate_actions"].append(
                        f"Investigate {len(critical_anomalies)} critical data anomalies"
                    )
            
            # Long-term strategic recommendations
            recommendations["long_term_strategies"].extend([
                "Implement comprehensive data governance framework",
                "Establish data quality center of excellence",
                "Deploy machine learning-based quality monitoring",
                "Create data quality training programs for all stakeholders"
            ])
            
            # Monitoring enhancements
            recommendations["monitoring_enhancements"].extend([
                "Set up real-time data quality dashboards",
                "Implement automated quality alerts and notifications",
                "Establish data quality KPIs and regular reporting",
                "Create data lineage tracking for quality issues"
            ])
            
            # Prioritize recommendations
            prioritized_recommendations = self._prioritize_recommendations(recommendations, recent_assessment)
            
            return {
                "action": "create_actionable_recommendations",
                "recommendations": recommendations,
                "prioritized_recommendations": prioritized_recommendations,
                "assessment_basis": {
                    "assessment_id": str(recent_assessment.id),
                    "overall_quality_score": recent_assessment.overall_quality_score,
                    "total_records": recent_assessment.total_records,
                    "critical_issues_count": len(recent_assessment.critical_issues)
                }
            }
            
        except Exception as e:
            error_msg = f"Failed to create actionable recommendations: {e}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    def _prioritize_recommendations(
        self, 
        recommendations: Dict[str, List[str]], 
        assessment: Assessment
    ) -> List[Dict[str, any]]:
        """Prioritize recommendations based on assessment results."""
        prioritized = []
        
        # High priority: immediate actions
        for action in recommendations["immediate_actions"]:
            prioritized.append({
                "recommendation": action,
                "priority": "high",
                "category": "immediate_action",
                "estimated_effort": "low",
                "expected_impact": "high"
            })
        
        # Medium priority: short-term improvements
        for improvement in recommendations["short_term_improvements"]:
            prioritized.append({
                "recommendation": improvement,
                "priority": "medium",
                "category": "short_term_improvement",
                "estimated_effort": "medium",
                "expected_impact": "medium"
            })
        
        # Lower priority: long-term strategies
        for strategy in recommendations["long_term_strategies"]:
            prioritized.append({
                "recommendation": strategy,
                "priority": "low",
                "category": "long_term_strategy",
                "estimated_effort": "high",
                "expected_impact": "high"
            })
        
        return prioritized[:10]  # Return top 10 prioritized recommendations
    
    async def _assess_completeness(self, data: List[EnrichedData]) -> CompletenessReport:
        """Internal method to assess data completeness."""
        return await self.completeness_checker.assess_completeness(data, self.required_fields)
    
    async def _assess_consistency(self, data: List[EnrichedData]) -> ConsistencyReport:
        """Internal method to assess data consistency."""
        return await self.consistency_validator.validate_consistency(data)
    
    async def _detect_anomalies(self, data: List[EnrichedData]) -> AnomalyReport:
        """Internal method to detect anomalies."""
        return await self.anomaly_detector.detect_anomalies(data)
    
    def _calculate_quality_metrics(
        self, 
        completeness_report: CompletenessReport,
        consistency_report: ConsistencyReport,
        anomaly_report: AnomalyReport
    ) -> List[QualityMetric]:
        """Calculate overall quality metrics from individual assessments."""
        metrics = []
        
        # Completeness metric
        completeness_threshold = self.quality_thresholds[QualityDimension.COMPLETENESS]
        metrics.append(QualityMetric(
            name="Data Completeness",
            dimension=QualityDimension.COMPLETENESS,
            value=completeness_report.overall_completeness_score,
            threshold=completeness_threshold,
            passed=completeness_report.overall_completeness_score >= completeness_threshold,
            description=f"Percentage of required fields populated across all records",
            details={
                "missing_required_fields": completeness_report.missing_required_fields,
                "critical_gaps_count": len(completeness_report.critical_gaps)
            }
        ))
        
        # Consistency metric
        consistency_threshold = self.quality_thresholds[QualityDimension.CONSISTENCY]
        metrics.append(QualityMetric(
            name="Data Consistency",
            dimension=QualityDimension.CONSISTENCY,
            value=consistency_report.overall_consistency_score,
            threshold=consistency_threshold,
            passed=consistency_report.overall_consistency_score >= consistency_threshold,
            description=f"Consistency of data values across different sources",
            details={
                "consistency_issues_count": len(consistency_report.consistency_issues),
                "sources_compared": consistency_report.sources_compared
            }
        ))
        
        # Anomaly metric (inverted - lower anomaly score is better)
        anomaly_threshold = 0.2  # Maximum acceptable anomaly rate
        anomaly_score = 1.0 - anomaly_report.overall_anomaly_score  # Invert for quality metric
        metrics.append(QualityMetric(
            name="Data Normality",
            dimension=QualityDimension.VALIDITY,
            value=anomaly_score,
            threshold=1.0 - anomaly_threshold,
            passed=anomaly_score >= (1.0 - anomaly_threshold),
            description=f"Absence of statistical outliers and anomalous values",
            details={
                "total_anomalies": len(anomaly_report.anomalies),
                "anomalies_by_severity": anomaly_report.anomalies_by_severity
            }
        ))
        
        return metrics
    
    def _calculate_overall_score(self, quality_metrics: List[QualityMetric]) -> float:
        """Calculate overall quality score from individual metrics."""
        if not quality_metrics:
            return 0.0
        
        # Weighted average of quality metrics
        weights = {
            QualityDimension.COMPLETENESS: 0.4,
            QualityDimension.CONSISTENCY: 0.3,
            QualityDimension.VALIDITY: 0.2,
            QualityDimension.ACCURACY: 0.1
        }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for metric in quality_metrics:
            weight = weights.get(metric.dimension, 0.1)
            weighted_sum += metric.value * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def _identify_critical_issues(
        self,
        completeness_report: CompletenessReport,
        consistency_report: ConsistencyReport,
        anomaly_report: AnomalyReport
    ) -> List[str]:
        """Identify critical issues requiring immediate attention."""
        critical_issues = []
        
        # Critical completeness issues
        if completeness_report.overall_completeness_score < 0.5:
            critical_issues.append(f"Severe data completeness issue: {completeness_report.overall_completeness_score:.1%} complete")
        
        if completeness_report.missing_required_fields:
            critical_issues.append(f"Missing required fields: {', '.join(completeness_report.missing_required_fields)}")
        
        # Critical consistency issues
        critical_consistency_issues = [
            issue for issue in consistency_report.consistency_issues 
            if issue.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]
        ]
        if critical_consistency_issues:
            critical_issues.append(f"High-severity consistency issues found: {len(critical_consistency_issues)} issues")
        
        # Critical anomalies
        critical_anomalies = [
            anomaly for anomaly in anomaly_report.anomalies
            if anomaly.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]
        ]
        if critical_anomalies:
            critical_issues.append(f"Critical anomalies detected: {len(critical_anomalies)} anomalies")
        
        return critical_issues
    
    def _generate_recommendations(
        self,
        completeness_report: CompletenessReport,
        consistency_report: ConsistencyReport,
        anomaly_report: AnomalyReport
    ) -> List[str]:
        """Generate actionable recommendations for data improvement."""
        recommendations = []
        
        # Completeness recommendations
        if completeness_report.overall_completeness_score < self.quality_thresholds[QualityDimension.COMPLETENESS]:
            recommendations.append("Improve data collection processes to capture missing required fields")
            
            if completeness_report.critical_gaps:
                recommendations.append(f"Focus on addressing critical data gaps in: {', '.join(completeness_report.critical_gaps[:3])}")
        
        # Consistency recommendations
        if consistency_report.overall_consistency_score < self.quality_thresholds[QualityDimension.CONSISTENCY]:
            recommendations.append("Implement data standardization rules to improve cross-source consistency")
            
            high_severity_issues = [
                issue for issue in consistency_report.consistency_issues
                if issue.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]
            ]
            if high_severity_issues:
                recommendations.append("Prioritize resolution of high-severity consistency issues")
        
        # Anomaly recommendations
        if anomaly_report.overall_anomaly_score > 0.2:
            recommendations.append("Investigate and resolve detected anomalies to improve data quality")
            
            if AnomalyType.FORMAT_ANOMALY in anomaly_report.anomalies_by_type:
                recommendations.append("Standardize data formats to reduce format-related anomalies")
        
        # General recommendations
        if not recommendations:
            recommendations.append("Data quality is good - continue monitoring and maintain current processes")
        else:
            recommendations.append("Implement automated quality monitoring to catch issues early")
            recommendations.append("Consider setting up data quality alerts for critical thresholds")
        
        return recommendations
    
    async def _store_assessment(self, assessment: Assessment) -> Dict:
        """Store quality assessment results."""
        if not self.storage_manager:
            return {"success": False, "error": "No storage manager configured"}
        
        try:
            # Store in quality assessments collection/table
            result = await self.storage_manager.store_quality_assessment(assessment)
            return {"success": True, "assessment_id": str(assessment.id)}
        except Exception as e:
            logger.error(f"Failed to store quality assessment: {e}")
            return {"success": False, "error": str(e)}