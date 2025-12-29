"""Quality report generator for comprehensive data quality reporting."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ...models.quality_assurance import (
    Assessment,
    QualityIssue,
    QualityReport,
    SeverityLevel,
)

logger = logging.getLogger(__name__)


class QualityReportGenerator:
    """Component for generating comprehensive quality reports."""
    
    def __init__(self):
        """Initialize the quality report generator."""
        self.name = "QualityReportGenerator"
        
        # Report templates and configurations
        self.report_templates = {
            "executive": {
                "focus": "high_level_summary",
                "include_technical_details": False,
                "max_issues_shown": 5
            },
            "technical": {
                "focus": "detailed_analysis",
                "include_technical_details": True,
                "max_issues_shown": 20
            },
            "operational": {
                "focus": "actionable_items",
                "include_technical_details": True,
                "max_issues_shown": 10
            }
        }
        
        logger.debug(f"Initialized {self.name}")
    
    def generate_quality_report(
        self, 
        assessments: List[Assessment],
        report_type: str = "technical",
        dataset_name: str = "Pharmaceutical Pipeline Data"
    ) -> QualityReport:
        """Generate a comprehensive quality report.
        
        Args:
            assessments: List of quality assessments
            report_type: Type of report ("executive", "technical", "operational")
            dataset_name: Name of the dataset being assessed
            
        Returns:
            QualityReport with comprehensive analysis and recommendations
        """
        logger.info(f"Generating {report_type} quality report for {len(assessments)} assessments")
        
        if not assessments:
            return self._create_empty_report(dataset_name)
        
        # Get the most recent assessment as primary
        primary_assessment = max(assessments, key=lambda a: a.assessed_at)
        
        # Calculate overall metrics
        overall_quality_score = self._calculate_overall_quality_score(assessments)
        quality_grade = self._determine_quality_grade(overall_quality_score)
        
        # Identify critical issues
        critical_issues = self._identify_critical_issues(assessments)
        
        # Generate executive summary
        executive_summary = self._generate_executive_summary(
            assessments, overall_quality_score, quality_grade, report_type
        )
        
        # Generate recommendations
        immediate_actions = self._generate_immediate_actions(critical_issues, assessments)
        improvement_recommendations = self._generate_improvement_recommendations(assessments)
        monitoring_suggestions = self._generate_monitoring_suggestions(assessments)
        
        # Calculate next assessment recommendation
        next_assessment_date = self._calculate_next_assessment_date(overall_quality_score)
        
        return QualityReport(
            report_title=f"{report_type.title()} Data Quality Report - {dataset_name}",
            dataset_name=dataset_name,
            assessment_id=primary_assessment.id,
            executive_summary=executive_summary,
            overall_quality_score=overall_quality_score,
            quality_grade=quality_grade,
            assessments=assessments,
            critical_issues=critical_issues,
            immediate_actions=immediate_actions,
            improvement_recommendations=improvement_recommendations,
            monitoring_suggestions=monitoring_suggestions,
            next_assessment_recommended=next_assessment_date
        )
    
    def _create_empty_report(self, dataset_name: str) -> QualityReport:
        """Create an empty report when no assessments are available."""
        return QualityReport(
            report_title=f"Data Quality Report - {dataset_name}",
            dataset_name=dataset_name,
            assessment_id=None,
            executive_summary="No quality assessments available for this dataset.",
            overall_quality_score=0.0,
            quality_grade="F",
            assessments=[],
            critical_issues=[],
            immediate_actions=["Perform initial data quality assessment"],
            improvement_recommendations=["Establish data quality monitoring"],
            monitoring_suggestions=["Set up automated quality checks"]
        )
    
    def _calculate_overall_quality_score(self, assessments: List[Assessment]) -> float:
        """Calculate overall quality score across all assessments."""
        if not assessments:
            return 0.0
        
        # Use the most recent assessment's score as primary
        recent_assessment = max(assessments, key=lambda a: a.assessed_at)
        return recent_assessment.overall_quality_score
    
    def _determine_quality_grade(self, score: float) -> str:
        """Determine quality grade based on score."""
        if score >= 0.9:
            return "A"
        elif score >= 0.8:
            return "B"
        elif score >= 0.7:
            return "C"
        elif score >= 0.6:
            return "D"
        else:
            return "F"
    
    def _identify_critical_issues(self, assessments: List[Assessment]) -> List[QualityIssue]:
        """Identify critical quality issues from assessments."""
        critical_issues = []
        
        for assessment in assessments:
            # Convert critical issues from assessment to QualityIssue objects
            for issue_text in assessment.critical_issues:
                critical_issue = QualityIssue(
                    issue_type="critical_quality_issue",
                    severity=SeverityLevel.CRITICAL,
                    dimension=self._infer_dimension_from_text(issue_text),
                    title=self._extract_title_from_issue(issue_text),
                    description=issue_text,
                    impact_assessment=self._assess_impact(issue_text),
                    recommended_actions=self._generate_issue_actions(issue_text),
                    requires_human_review=True
                )
                critical_issues.append(critical_issue)
            
            # Add issues from completeness report
            if assessment.completeness_report:
                for gap in assessment.completeness_report.critical_gaps:
                    critical_issue = QualityIssue(
                        issue_type="completeness_gap",
                        severity=SeverityLevel.HIGH,
                        dimension="completeness",
                        title=f"Critical Data Gap: {gap}",
                        description=f"Field '{gap}' has critical completeness issues",
                        impact_assessment="Missing required data affects analysis reliability",
                        recommended_actions=[
                            f"Improve data collection for field '{gap}'",
                            "Review data source quality",
                            "Implement validation rules"
                        ],
                        requires_human_review=True
                    )
                    critical_issues.append(critical_issue)
            
            # Add issues from consistency report
            if assessment.consistency_report:
                high_severity_issues = [
                    issue for issue in assessment.consistency_report.consistency_issues
                    if issue.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]
                ]
                
                for consistency_issue in high_severity_issues:
                    critical_issue = QualityIssue(
                        issue_type="consistency_issue",
                        severity=consistency_issue.severity,
                        dimension="consistency",
                        title=f"Consistency Issue: {consistency_issue.field_name}",
                        description=consistency_issue.description,
                        affected_records=consistency_issue.affected_records,
                        affected_fields=[consistency_issue.field_name],
                        impact_assessment="Inconsistent data affects cross-source analysis",
                        recommended_actions=[
                            "Standardize data formats across sources",
                            "Implement data validation rules",
                            "Review data collection processes"
                        ],
                        requires_human_review=consistency_issue.severity == SeverityLevel.CRITICAL
                    )
                    critical_issues.append(critical_issue)
            
            # Add critical anomalies
            if assessment.anomaly_report:
                critical_anomalies = [
                    anomaly for anomaly in assessment.anomaly_report.anomalies
                    if anomaly.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]
                ]
                
                for anomaly in critical_anomalies:
                    critical_issue = QualityIssue(
                        issue_type="data_anomaly",
                        severity=anomaly.severity,
                        dimension="validity",
                        title=f"Data Anomaly: {anomaly.field_name}",
                        description=anomaly.description,
                        affected_records=[anomaly.record_id],
                        affected_fields=[anomaly.field_name],
                        impact_assessment="Anomalous data may indicate quality issues",
                        recommended_actions=[
                            "Investigate anomalous values",
                            "Review data collection process",
                            "Implement outlier detection"
                        ],
                        requires_human_review=anomaly.severity == SeverityLevel.CRITICAL
                    )
                    critical_issues.append(critical_issue)
        
        # Sort by severity and limit to most critical
        critical_issues.sort(key=lambda x: (x.severity.value, x.created_at), reverse=True)
        return critical_issues[:20]  # Limit to top 20 issues
    
    def _infer_dimension_from_text(self, issue_text: str) -> str:
        """Infer quality dimension from issue text."""
        text_lower = issue_text.lower()
        
        if any(word in text_lower for word in ["complete", "missing", "empty", "null"]):
            return "completeness"
        elif any(word in text_lower for word in ["consistent", "conflict", "mismatch"]):
            return "consistency"
        elif any(word in text_lower for word in ["anomal", "outlier", "unusual"]):
            return "validity"
        elif any(word in text_lower for word in ["accurate", "correct", "reference"]):
            return "accuracy"
        else:
            return "general"
    
    def _extract_title_from_issue(self, issue_text: str) -> str:
        """Extract a concise title from issue text."""
        # Take first sentence or first 60 characters
        sentences = issue_text.split('.')
        if sentences:
            title = sentences[0].strip()
            if len(title) > 60:
                title = title[:57] + "..."
            return title
        return issue_text[:60] + "..." if len(issue_text) > 60 else issue_text
    
    def _assess_impact(self, issue_text: str) -> str:
        """Assess the impact of a quality issue."""
        text_lower = issue_text.lower()
        
        if "severe" in text_lower or "critical" in text_lower:
            return "High impact: Significantly affects data reliability and analysis accuracy"
        elif "missing required" in text_lower:
            return "Medium-High impact: Affects completeness of analysis and reporting"
        elif "consistency" in text_lower:
            return "Medium impact: May lead to conflicting results in cross-source analysis"
        elif "anomal" in text_lower or "outlier" in text_lower:
            return "Low-Medium impact: May indicate data quality issues requiring investigation"
        else:
            return "Impact assessment required: Manual review needed to determine severity"
    
    def _generate_issue_actions(self, issue_text: str) -> List[str]:
        """Generate recommended actions for a quality issue."""
        text_lower = issue_text.lower()
        actions = []
        
        if "complete" in text_lower or "missing" in text_lower:
            actions.extend([
                "Review data collection processes",
                "Implement data validation rules",
                "Contact data sources for missing information"
            ])
        
        if "consistency" in text_lower:
            actions.extend([
                "Standardize data formats across sources",
                "Implement cross-source validation",
                "Create data mapping documentation"
            ])
        
        if "anomal" in text_lower or "outlier" in text_lower:
            actions.extend([
                "Investigate anomalous values",
                "Review data entry processes",
                "Implement automated outlier detection"
            ])
        
        if not actions:
            actions = [
                "Conduct detailed investigation",
                "Review data quality processes",
                "Implement monitoring and alerts"
            ]
        
        return actions[:3]  # Limit to top 3 actions
    
    def _generate_executive_summary(
        self, 
        assessments: List[Assessment], 
        overall_score: float, 
        quality_grade: str,
        report_type: str
    ) -> str:
        """Generate executive summary based on assessments."""
        recent_assessment = max(assessments, key=lambda a: a.assessed_at)
        
        # Count critical issues
        total_critical_issues = sum(len(a.critical_issues) for a in assessments)
        
        # Determine overall status
        if overall_score >= 0.8:
            status = "good"
            status_desc = "meets quality standards"
        elif overall_score >= 0.6:
            status = "acceptable"
            status_desc = "has some quality concerns that should be addressed"
        else:
            status = "poor"
            status_desc = "has significant quality issues requiring immediate attention"
        
        # Generate summary based on report type
        if report_type == "executive":
            summary = f"""
Data quality assessment shows {status} overall quality with a score of {overall_score:.1%} (Grade {quality_grade}).
The dataset {status_desc}. {total_critical_issues} critical issues were identified that require attention.
Key areas for improvement include data completeness, cross-source consistency, and anomaly resolution.
            """.strip()
        
        elif report_type == "operational":
            summary = f"""
Operational Quality Assessment: {overall_score:.1%} overall score (Grade {quality_grade}).
{total_critical_issues} critical issues identified requiring immediate action.
Primary focus areas: {', '.join(self._get_top_problem_areas(assessments))}.
Recommended next assessment: {self._calculate_next_assessment_date(overall_score).strftime('%Y-%m-%d')}.
            """.strip()
        
        else:  # technical
            completeness_score = recent_assessment.completeness_report.overall_completeness_score if recent_assessment.completeness_report else 0.0
            consistency_score = recent_assessment.consistency_report.overall_consistency_score if recent_assessment.consistency_report else 0.0
            anomaly_score = recent_assessment.anomaly_report.overall_anomaly_score if recent_assessment.anomaly_report else 0.0
            
            summary = f"""
Technical Quality Assessment Results:
- Overall Quality Score: {overall_score:.1%} (Grade {quality_grade})
- Data Completeness: {completeness_score:.1%}
- Cross-Source Consistency: {consistency_score:.1%}
- Anomaly Rate: {anomaly_score:.1%}
- Total Records Analyzed: {recent_assessment.total_records:,}
- Critical Issues: {total_critical_issues}

The assessment indicates {status} data quality. {self._get_technical_summary_details(assessments)}
            """.strip()
        
        return summary
    
    def _get_top_problem_areas(self, assessments: List[Assessment]) -> List[str]:
        """Get top problem areas from assessments."""
        problem_areas = []
        
        recent_assessment = max(assessments, key=lambda a: a.assessed_at)
        
        if recent_assessment.completeness_report and recent_assessment.completeness_report.overall_completeness_score < 0.8:
            problem_areas.append("data completeness")
        
        if recent_assessment.consistency_report and recent_assessment.consistency_report.overall_consistency_score < 0.8:
            problem_areas.append("cross-source consistency")
        
        if recent_assessment.anomaly_report and recent_assessment.anomaly_report.overall_anomaly_score > 0.2:
            problem_areas.append("data anomalies")
        
        return problem_areas[:3] if problem_areas else ["general data quality"]
    
    def _get_technical_summary_details(self, assessments: List[Assessment]) -> str:
        """Get technical details for summary."""
        recent_assessment = max(assessments, key=lambda a: a.assessed_at)
        details = []
        
        if recent_assessment.completeness_report:
            missing_fields = len(recent_assessment.completeness_report.missing_required_fields)
            if missing_fields > 0:
                details.append(f"{missing_fields} required fields have completeness issues")
        
        if recent_assessment.consistency_report:
            consistency_issues = len(recent_assessment.consistency_report.consistency_issues)
            if consistency_issues > 0:
                details.append(f"{consistency_issues} consistency issues detected")
        
        if recent_assessment.anomaly_report:
            anomalies = len(recent_assessment.anomaly_report.anomalies)
            if anomalies > 0:
                details.append(f"{anomalies} anomalies identified")
        
        return ". ".join(details) + "." if details else "No major issues detected."
    
    def _generate_immediate_actions(
        self, 
        critical_issues: List[QualityIssue], 
        assessments: List[Assessment]
    ) -> List[str]:
        """Generate immediate actions based on critical issues."""
        actions = []
        
        # Actions based on critical issues
        if critical_issues:
            severity_counts = {}
            for issue in critical_issues:
                severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
            
            if SeverityLevel.CRITICAL in severity_counts:
                actions.append(f"Address {severity_counts[SeverityLevel.CRITICAL]} critical data quality issues immediately")
            
            if SeverityLevel.HIGH in severity_counts:
                actions.append(f"Resolve {severity_counts[SeverityLevel.HIGH]} high-priority quality issues within 48 hours")
        
        # Actions based on assessment results
        recent_assessment = max(assessments, key=lambda a: a.assessed_at) if assessments else None
        
        if recent_assessment:
            if recent_assessment.overall_quality_score < 0.5:
                actions.append("Halt data processing until critical quality issues are resolved")
            
            if recent_assessment.completeness_report and recent_assessment.completeness_report.overall_completeness_score < 0.6:
                actions.append("Implement immediate data collection improvements for missing required fields")
            
            if recent_assessment.consistency_report and recent_assessment.consistency_report.overall_consistency_score < 0.6:
                actions.append("Standardize data formats and resolve cross-source inconsistencies")
        
        # Default actions if none specific
        if not actions:
            actions = [
                "Continue monitoring data quality metrics",
                "Maintain current data quality processes",
                "Schedule next quality assessment"
            ]
        
        return actions[:5]  # Limit to top 5 actions
    
    def _generate_improvement_recommendations(self, assessments: List[Assessment]) -> List[str]:
        """Generate long-term improvement recommendations."""
        recommendations = []
        
        recent_assessment = max(assessments, key=lambda a: a.assessed_at) if assessments else None
        
        if recent_assessment:
            # Completeness recommendations
            if recent_assessment.completeness_report and recent_assessment.completeness_report.overall_completeness_score < 0.9:
                recommendations.append("Implement automated data validation at collection points")
                recommendations.append("Establish data quality SLAs with source systems")
            
            # Consistency recommendations
            if recent_assessment.consistency_report and recent_assessment.consistency_report.overall_consistency_score < 0.9:
                recommendations.append("Develop standardized data dictionaries across all sources")
                recommendations.append("Implement master data management practices")
            
            # Anomaly recommendations
            if recent_assessment.anomaly_report and recent_assessment.anomaly_report.overall_anomaly_score > 0.1:
                recommendations.append("Deploy automated anomaly detection and alerting")
                recommendations.append("Establish data profiling and monitoring dashboards")
        
        # General recommendations
        recommendations.extend([
            "Implement continuous data quality monitoring",
            "Establish data quality metrics and KPIs",
            "Create data quality training programs for data stewards",
            "Develop data quality incident response procedures"
        ])
        
        return recommendations[:8]  # Limit to top 8 recommendations
    
    def _generate_monitoring_suggestions(self, assessments: List[Assessment]) -> List[str]:
        """Generate monitoring suggestions."""
        suggestions = [
            "Set up automated daily data quality checks",
            "Implement real-time data quality alerts for critical issues",
            "Create data quality dashboards for stakeholders",
            "Establish weekly data quality review meetings",
            "Monitor data quality trends over time",
            "Set up automated reporting for quality metrics",
            "Implement data lineage tracking for quality issues",
            "Create data quality scorecards for different data sources"
        ]
        
        return suggestions[:6]  # Limit to top 6 suggestions
    
    def _calculate_next_assessment_date(self, quality_score: float) -> datetime:
        """Calculate when the next assessment should be performed."""
        base_date = datetime.utcnow()
        
        if quality_score < 0.5:
            # Poor quality - assess weekly
            return base_date + timedelta(days=7)
        elif quality_score < 0.7:
            # Fair quality - assess bi-weekly
            return base_date + timedelta(days=14)
        elif quality_score < 0.9:
            # Good quality - assess monthly
            return base_date + timedelta(days=30)
        else:
            # Excellent quality - assess quarterly
            return base_date + timedelta(days=90)