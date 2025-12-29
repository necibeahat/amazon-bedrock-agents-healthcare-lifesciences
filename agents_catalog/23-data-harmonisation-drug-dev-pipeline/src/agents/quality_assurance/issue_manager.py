"""Issue management system for tracking and resolving data quality issues."""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from ...models.quality_assurance import (
    QualityIssue,
    SeverityLevel,
)

logger = logging.getLogger(__name__)


class IssueStatus(str, Enum):
    """Status of a quality issue."""
    
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    DEFERRED = "deferred"


class IssuePriority(str, Enum):
    """Priority level for issue resolution."""
    
    URGENT = "urgent"      # Resolve within 4 hours
    HIGH = "high"          # Resolve within 24 hours
    MEDIUM = "medium"      # Resolve within 1 week
    LOW = "low"            # Resolve within 1 month


class IssueResolution(BaseModel):
    """Resolution details for a quality issue."""
    
    resolution_type: str
    description: str
    resolved_by: str
    resolved_at: datetime = Field(default_factory=datetime.utcnow)
    verification_required: bool = False
    verification_completed: bool = False


class ManagedQualityIssue(BaseModel):
    """Extended quality issue with management metadata."""
    
    id: UUID = Field(default_factory=uuid4)
    original_issue: QualityIssue
    status: IssueStatus = IssueStatus.OPEN
    priority: IssuePriority
    assigned_to: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    due_date: Optional[datetime] = None
    resolution: Optional[IssueResolution] = None
    
    # Tracking and escalation
    escalation_level: int = 0
    escalated_at: Optional[datetime] = None
    last_reminder_sent: Optional[datetime] = None
    
    # Related issues and dependencies
    related_issues: List[UUID] = Field(default_factory=list)
    blocks_issues: List[UUID] = Field(default_factory=list)
    blocked_by_issues: List[UUID] = Field(default_factory=list)
    
    # Comments and updates
    comments: List[str] = Field(default_factory=list)
    
    def add_comment(self, comment: str, author: str = "system"):
        """Add a comment to the issue."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        formatted_comment = f"[{timestamp}] {author}: {comment}"
        self.comments.append(formatted_comment)
        self.updated_at = datetime.utcnow()


class IssueManager:
    """Manager for tracking and resolving data quality issues."""
    
    def __init__(self):
        """Initialize the issue manager."""
        self.name = "IssueManager"
        
        # In-memory storage (in production, this would be a database)
        self.issues: Dict[UUID, ManagedQualityIssue] = {}
        
        # Configuration
        self.auto_escalation_enabled = True
        self.escalation_thresholds = {
            IssuePriority.URGENT: timedelta(hours=4),
            IssuePriority.HIGH: timedelta(hours=24),
            IssuePriority.MEDIUM: timedelta(days=7),
            IssuePriority.LOW: timedelta(days=30)
        }
        
        # Notification settings
        self.notification_enabled = True
        self.reminder_intervals = {
            IssuePriority.URGENT: timedelta(hours=1),
            IssuePriority.HIGH: timedelta(hours=4),
            IssuePriority.MEDIUM: timedelta(days=1),
            IssuePriority.LOW: timedelta(days=7)
        }
        
        logger.debug(f"Initialized {self.name}")
    
    def create_issue(
        self, 
        quality_issue: QualityIssue, 
        assigned_to: Optional[str] = None
    ) -> ManagedQualityIssue:
        """Create a new managed quality issue.
        
        Args:
            quality_issue: Original quality issue
            assigned_to: Optional assignee
            
        Returns:
            ManagedQualityIssue with management metadata
        """
        # Determine priority based on severity
        priority = self._determine_priority(quality_issue.severity)
        
        # Calculate due date
        due_date = self._calculate_due_date(priority)
        
        # Create managed issue
        managed_issue = ManagedQualityIssue(
            original_issue=quality_issue,
            priority=priority,
            assigned_to=assigned_to,
            due_date=due_date
        )
        
        # Add initial comment
        managed_issue.add_comment(f"Issue created with {priority.value} priority")
        
        # Store the issue
        self.issues[managed_issue.id] = managed_issue
        
        logger.info(f"Created issue {managed_issue.id} with priority {priority.value}")
        
        return managed_issue
    
    def update_issue_status(
        self, 
        issue_id: UUID, 
        new_status: IssueStatus,
        comment: Optional[str] = None,
        updated_by: str = "system"
    ) -> bool:
        """Update the status of an issue.
        
        Args:
            issue_id: ID of the issue to update
            new_status: New status for the issue
            comment: Optional comment about the status change
            updated_by: Who updated the status
            
        Returns:
            True if update was successful, False otherwise
        """
        if issue_id not in self.issues:
            logger.warning(f"Issue {issue_id} not found")
            return False
        
        issue = self.issues[issue_id]
        old_status = issue.status
        
        issue.status = new_status
        issue.updated_at = datetime.utcnow()
        
        # Add status change comment
        status_comment = f"Status changed from {old_status.value} to {new_status.value}"
        if comment:
            status_comment += f": {comment}"
        
        issue.add_comment(status_comment, updated_by)
        
        logger.info(f"Updated issue {issue_id} status to {new_status.value}")
        
        return True
    
    def resolve_issue(
        self, 
        issue_id: UUID, 
        resolution_type: str,
        description: str,
        resolved_by: str,
        verification_required: bool = False
    ) -> bool:
        """Resolve an issue.
        
        Args:
            issue_id: ID of the issue to resolve
            resolution_type: Type of resolution
            description: Description of the resolution
            resolved_by: Who resolved the issue
            verification_required: Whether verification is needed
            
        Returns:
            True if resolution was successful, False otherwise
        """
        if issue_id not in self.issues:
            logger.warning(f"Issue {issue_id} not found")
            return False
        
        issue = self.issues[issue_id]
        
        # Create resolution
        resolution = IssueResolution(
            resolution_type=resolution_type,
            description=description,
            resolved_by=resolved_by,
            verification_required=verification_required
        )
        
        issue.resolution = resolution
        issue.status = IssueStatus.RESOLVED
        issue.updated_at = datetime.utcnow()
        
        # Add resolution comment
        issue.add_comment(f"Issue resolved: {description}", resolved_by)
        
        logger.info(f"Resolved issue {issue_id} by {resolved_by}")
        
        return True
    
    def assign_issue(
        self, 
        issue_id: UUID, 
        assigned_to: str,
        assigned_by: str = "system"
    ) -> bool:
        """Assign an issue to someone.
        
        Args:
            issue_id: ID of the issue to assign
            assigned_to: Who to assign the issue to
            assigned_by: Who made the assignment
            
        Returns:
            True if assignment was successful, False otherwise
        """
        if issue_id not in self.issues:
            logger.warning(f"Issue {issue_id} not found")
            return False
        
        issue = self.issues[issue_id]
        old_assignee = issue.assigned_to
        
        issue.assigned_to = assigned_to
        issue.updated_at = datetime.utcnow()
        
        # Add assignment comment
        if old_assignee:
            comment = f"Reassigned from {old_assignee} to {assigned_to}"
        else:
            comment = f"Assigned to {assigned_to}"
        
        issue.add_comment(comment, assigned_by)
        
        logger.info(f"Assigned issue {issue_id} to {assigned_to}")
        
        return True
    
    def escalate_issue(
        self, 
        issue_id: UUID, 
        escalation_reason: str,
        escalated_by: str = "system"
    ) -> bool:
        """Escalate an issue.
        
        Args:
            issue_id: ID of the issue to escalate
            escalation_reason: Reason for escalation
            escalated_by: Who escalated the issue
            
        Returns:
            True if escalation was successful, False otherwise
        """
        if issue_id not in self.issues:
            logger.warning(f"Issue {issue_id} not found")
            return False
        
        issue = self.issues[issue_id]
        
        issue.escalation_level += 1
        issue.escalated_at = datetime.utcnow()
        issue.updated_at = datetime.utcnow()
        
        # Increase priority if possible
        if issue.priority == IssuePriority.LOW:
            issue.priority = IssuePriority.MEDIUM
        elif issue.priority == IssuePriority.MEDIUM:
            issue.priority = IssuePriority.HIGH
        elif issue.priority == IssuePriority.HIGH:
            issue.priority = IssuePriority.URGENT
        
        # Update due date based on new priority
        issue.due_date = self._calculate_due_date(issue.priority)
        
        # Add escalation comment
        issue.add_comment(f"Issue escalated (level {issue.escalation_level}): {escalation_reason}", escalated_by)
        
        logger.warning(f"Escalated issue {issue_id} to level {issue.escalation_level}")
        
        return True
    
    def get_overdue_issues(self) -> List[ManagedQualityIssue]:
        """Get all overdue issues.
        
        Returns:
            List of overdue issues
        """
        now = datetime.utcnow()
        overdue_issues = []
        
        for issue in self.issues.values():
            if (issue.status in [IssueStatus.OPEN, IssueStatus.IN_PROGRESS] and 
                issue.due_date and 
                now > issue.due_date):
                overdue_issues.append(issue)
        
        # Sort by how overdue they are
        overdue_issues.sort(key=lambda x: now - x.due_date, reverse=True)
        
        return overdue_issues
    
    def get_issues_by_priority(self, priority: IssuePriority) -> List[ManagedQualityIssue]:
        """Get issues by priority level.
        
        Args:
            priority: Priority level to filter by
            
        Returns:
            List of issues with the specified priority
        """
        return [
            issue for issue in self.issues.values()
            if issue.priority == priority and issue.status != IssueStatus.CLOSED
        ]
    
    def get_issues_by_status(self, status: IssueStatus) -> List[ManagedQualityIssue]:
        """Get issues by status.
        
        Args:
            status: Status to filter by
            
        Returns:
            List of issues with the specified status
        """
        return [issue for issue in self.issues.values() if issue.status == status]
    
    def get_issues_requiring_attention(self) -> Dict[str, List[ManagedQualityIssue]]:
        """Get issues that require immediate attention.
        
        Returns:
            Dictionary categorizing issues that need attention
        """
        now = datetime.utcnow()
        
        return {
            "overdue": self.get_overdue_issues(),
            "urgent": self.get_issues_by_priority(IssuePriority.URGENT),
            "escalated": [
                issue for issue in self.issues.values()
                if issue.escalation_level > 0 and issue.status != IssueStatus.CLOSED
            ],
            "unassigned_high_priority": [
                issue for issue in self.issues.values()
                if (issue.assigned_to is None and 
                    issue.priority in [IssuePriority.URGENT, IssuePriority.HIGH] and
                    issue.status in [IssueStatus.OPEN, IssueStatus.IN_PROGRESS])
            ],
            "pending_verification": [
                issue for issue in self.issues.values()
                if (issue.resolution and 
                    issue.resolution.verification_required and 
                    not issue.resolution.verification_completed)
            ]
        }
    
    def process_automatic_escalations(self) -> List[UUID]:
        """Process automatic escalations for overdue issues.
        
        Returns:
            List of issue IDs that were escalated
        """
        if not self.auto_escalation_enabled:
            return []
        
        escalated_issues = []
        overdue_issues = self.get_overdue_issues()
        
        for issue in overdue_issues:
            # Check if enough time has passed since last escalation
            time_since_escalation = datetime.utcnow() - (issue.escalated_at or issue.created_at)
            escalation_threshold = self.escalation_thresholds.get(issue.priority, timedelta(days=1))
            
            if time_since_escalation >= escalation_threshold:
                escalation_reason = f"Issue overdue by {datetime.utcnow() - issue.due_date}"
                if self.escalate_issue(issue.id, escalation_reason, "auto-escalation"):
                    escalated_issues.append(issue.id)
        
        return escalated_issues
    
    def generate_issue_summary(self) -> Dict[str, any]:
        """Generate a summary of all issues.
        
        Returns:
            Dictionary with issue statistics and summaries
        """
        total_issues = len(self.issues)
        
        # Count by status
        status_counts = {}
        for status in IssueStatus:
            status_counts[status.value] = len(self.get_issues_by_status(status))
        
        # Count by priority
        priority_counts = {}
        for priority in IssuePriority:
            priority_counts[priority.value] = len(self.get_issues_by_priority(priority))
        
        # Get attention-requiring issues
        attention_issues = self.get_issues_requiring_attention()
        
        return {
            "total_issues": total_issues,
            "status_breakdown": status_counts,
            "priority_breakdown": priority_counts,
            "overdue_count": len(attention_issues["overdue"]),
            "urgent_count": len(attention_issues["urgent"]),
            "escalated_count": len(attention_issues["escalated"]),
            "unassigned_high_priority_count": len(attention_issues["unassigned_high_priority"]),
            "pending_verification_count": len(attention_issues["pending_verification"]),
            "issues_requiring_attention": {
                key: len(issues) for key, issues in attention_issues.items()
            }
        }
    
    def _determine_priority(self, severity: SeverityLevel) -> IssuePriority:
        """Determine priority based on severity level."""
        if severity == SeverityLevel.CRITICAL:
            return IssuePriority.URGENT
        elif severity == SeverityLevel.HIGH:
            return IssuePriority.HIGH
        elif severity == SeverityLevel.MEDIUM:
            return IssuePriority.MEDIUM
        else:
            return IssuePriority.LOW
    
    def _calculate_due_date(self, priority: IssuePriority) -> datetime:
        """Calculate due date based on priority."""
        now = datetime.utcnow()
        
        if priority == IssuePriority.URGENT:
            return now + timedelta(hours=4)
        elif priority == IssuePriority.HIGH:
            return now + timedelta(hours=24)
        elif priority == IssuePriority.MEDIUM:
            return now + timedelta(days=7)
        else:  # LOW
            return now + timedelta(days=30)