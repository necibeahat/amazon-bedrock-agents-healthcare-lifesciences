"""
Error handling and recovery strategies for multi-agent orchestration.

This module implements comprehensive error handling, retry mechanisms,
and recovery strategies for the pharmaceutical pipeline system.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict

from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)

from ..models.pipeline import PipelineTask, TaskStatus, AgentHealth
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Categories of errors."""
    NETWORK = "network"
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    RESOURCE = "resource"
    AGENT = "agent"
    SYSTEM = "system"
    DATA = "data"
    CONFIGURATION = "configuration"


class RecoveryStrategy(Enum):
    """Recovery strategies for different error types."""
    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    ABORT = "abort"
    ESCALATE = "escalate"
    RESTART = "restart"


@dataclass
class ErrorContext:
    """
    Context information for an error.
    
    Attributes:
        error: The original exception
        task_id: ID of the task that failed
        agent_name: Name of the agent that encountered the error
        timestamp: When the error occurred
        severity: Error severity level
        category: Error category
        retry_count: Number of retry attempts made
        metadata: Additional error metadata
    """
    error: Exception
    task_id: Optional[str] = None
    agent_name: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    category: ErrorCategory = ErrorCategory.SYSTEM
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryAction:
    """
    Defines a recovery action for an error.
    
    Attributes:
        strategy: Recovery strategy to use
        handler: Function to execute the recovery
        max_attempts: Maximum number of recovery attempts
        delay: Delay between recovery attempts
        conditions: Conditions that must be met for this action
    """
    strategy: RecoveryStrategy
    handler: Callable[[ErrorContext], Any]
    max_attempts: int = 3
    delay: float = 1.0
    conditions: Dict[str, Any] = field(default_factory=dict)


class ErrorHandler:
    """
    Comprehensive error handling system for multi-agent orchestration.
    
    Provides error classification, recovery strategies, retry mechanisms,
    and escalation procedures for different types of failures.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the error handler.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Error tracking
        self.error_history: List[ErrorContext] = []
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.recovery_actions: Dict[ErrorCategory, List[RecoveryAction]] = defaultdict(list)
        
        # Circuit breaker state
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
        # Recovery handlers
        self.recovery_handlers: Dict[RecoveryStrategy, Callable] = {}
        
        # Initialize default recovery actions
        self._setup_default_recovery_actions()
        self._setup_recovery_handlers()
        
        logger.info("Error handler initialized")
    
    def _setup_default_recovery_actions(self) -> None:
        """Set up default recovery actions for different error categories."""
        
        # Network errors - retry with exponential backoff
        self.recovery_actions[ErrorCategory.NETWORK].append(
            RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                handler=self._retry_with_backoff,
                max_attempts=3,
                delay=1.0
            )
        )
        
        # Timeout errors - retry with increased timeout
        self.recovery_actions[ErrorCategory.TIMEOUT].append(
            RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                handler=self._retry_with_timeout_increase,
                max_attempts=2,
                delay=2.0
            )
        )
        
        # Resource errors - wait and retry
        self.recovery_actions[ErrorCategory.RESOURCE].append(
            RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                handler=self._retry_after_resource_wait,
                max_attempts=3,
                delay=5.0
            )
        )
        
        # Agent errors - restart agent
        self.recovery_actions[ErrorCategory.AGENT].append(
            RecoveryAction(
                strategy=RecoveryStrategy.RESTART,
                handler=self._restart_agent,
                max_attempts=2,
                delay=10.0
            )
        )
        
        # Validation errors - skip or fallback
        self.recovery_actions[ErrorCategory.VALIDATION].append(
            RecoveryAction(
                strategy=RecoveryStrategy.FALLBACK,
                handler=self._use_fallback_validation,
                max_attempts=1,
                delay=0.0
            )
        )
        
        # Critical system errors - escalate
        self.recovery_actions[ErrorCategory.SYSTEM].append(
            RecoveryAction(
                strategy=RecoveryStrategy.ESCALATE,
                handler=self._escalate_error,
                max_attempts=1,
                delay=0.0
            )
        )
    
    def _setup_recovery_handlers(self) -> None:
        """Set up recovery strategy handlers."""
        self.recovery_handlers = {
            RecoveryStrategy.RETRY: self._handle_retry,
            RecoveryStrategy.FALLBACK: self._handle_fallback,
            RecoveryStrategy.SKIP: self._handle_skip,
            RecoveryStrategy.ABORT: self._handle_abort,
            RecoveryStrategy.ESCALATE: self._handle_escalate,
            RecoveryStrategy.RESTART: self._handle_restart
        }
    
    async def handle_error(
        self,
        error: Exception,
        task_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Handle an error with appropriate recovery strategy.
        
        Args:
            error: The exception that occurred
            task_id: ID of the task that failed
            agent_name: Name of the agent that encountered the error
            metadata: Additional error metadata
            
        Returns:
            True if error was handled successfully, False otherwise
        """
        # Create error context
        error_context = ErrorContext(
            error=error,
            task_id=task_id,
            agent_name=agent_name,
            metadata=metadata or {}
        )
        
        # Classify the error
        error_context.category = self._classify_error(error)
        error_context.severity = self._assess_severity(error, error_context.category)
        
        # Record the error
        self.error_history.append(error_context)
        error_key = f"{error_context.category.value}:{type(error).__name__}"
        self.error_counts[error_key] += 1
        
        logger.error(
            f"Handling error: {error} (Category: {error_context.category.value}, "
            f"Severity: {error_context.severity.value})"
        )
        
        # Check circuit breaker
        if self._is_circuit_breaker_open(agent_name, error_context.category):
            logger.warning(f"Circuit breaker open for {agent_name}:{error_context.category.value}")
            return False
        
        # Try recovery actions
        recovery_successful = await self._attempt_recovery(error_context)
        
        # Update circuit breaker state
        self._update_circuit_breaker(agent_name, error_context.category, recovery_successful)
        
        return recovery_successful
    
    def _classify_error(self, error: Exception) -> ErrorCategory:
        """
        Classify an error into a category.
        
        Args:
            error: The exception to classify
            
        Returns:
            Error category
        """
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Network-related errors
        if any(keyword in error_message for keyword in [
            'connection', 'network', 'dns', 'socket', 'http', 'ssl', 'certificate'
        ]) or error_type in ['ConnectionError', 'HTTPError', 'SSLError']:
            return ErrorCategory.NETWORK
        
        # Timeout errors
        if 'timeout' in error_message or error_type in ['TimeoutError', 'asyncio.TimeoutError']:
            return ErrorCategory.TIMEOUT
        
        # Resource errors
        if any(keyword in error_message for keyword in [
            'memory', 'disk', 'space', 'resource', 'limit', 'quota'
        ]) or error_type in ['MemoryError', 'OSError']:
            return ErrorCategory.RESOURCE
        
        # Validation errors
        if any(keyword in error_message for keyword in [
            'validation', 'invalid', 'format', 'schema', 'parse'
        ]) or error_type in ['ValidationError', 'ValueError', 'JSONDecodeError']:
            return ErrorCategory.VALIDATION
        
        # Data errors
        if any(keyword in error_message for keyword in [
            'data', 'missing', 'empty', 'corrupt', 'integrity'
        ]) or error_type in ['KeyError', 'IndexError', 'AttributeError']:
            return ErrorCategory.DATA
        
        # Configuration errors
        if any(keyword in error_message for keyword in [
            'config', 'setting', 'parameter', 'environment'
        ]) or error_type in ['ConfigurationError']:
            return ErrorCategory.CONFIGURATION
        
        # Agent-specific errors
        if 'agent' in error_message:
            return ErrorCategory.AGENT
        
        # Default to system error
        return ErrorCategory.SYSTEM
    
    def _assess_severity(self, error: Exception, category: ErrorCategory) -> ErrorSeverity:
        """
        Assess the severity of an error.
        
        Args:
            error: The exception
            category: Error category
            
        Returns:
            Error severity level
        """
        error_message = str(error).lower()
        
        # Critical errors
        if any(keyword in error_message for keyword in [
            'critical', 'fatal', 'corrupt', 'security'
        ]) or category == ErrorCategory.SYSTEM:
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if any(keyword in error_message for keyword in [
            'failed', 'error', 'exception', 'abort'
        ]) or category in [ErrorCategory.AGENT, ErrorCategory.RESOURCE]:
            return ErrorSeverity.HIGH
        
        # Medium severity errors
        if category in [ErrorCategory.NETWORK, ErrorCategory.TIMEOUT, ErrorCategory.DATA]:
            return ErrorSeverity.MEDIUM
        
        # Low severity errors
        return ErrorSeverity.LOW
    
    async def _attempt_recovery(self, error_context: ErrorContext) -> bool:
        """
        Attempt recovery using available strategies.
        
        Args:
            error_context: Error context information
            
        Returns:
            True if recovery was successful
        """
        recovery_actions = self.recovery_actions.get(error_context.category, [])
        
        for action in recovery_actions:
            try:
                logger.info(f"Attempting recovery strategy: {action.strategy.value}")
                
                # Check if conditions are met
                if not self._check_recovery_conditions(error_context, action):
                    continue
                
                # Execute recovery action
                success = await action.handler(error_context)
                
                if success:
                    logger.info(f"Recovery successful using strategy: {action.strategy.value}")
                    return True
                
            except Exception as recovery_error:
                logger.error(f"Recovery action failed: {recovery_error}")
                continue
        
        logger.warning(f"All recovery attempts failed for error: {error_context.error}")
        return False
    
    def _check_recovery_conditions(
        self,
        error_context: ErrorContext,
        action: RecoveryAction
    ) -> bool:
        """
        Check if conditions are met for a recovery action.
        
        Args:
            error_context: Error context
            action: Recovery action
            
        Returns:
            True if conditions are met
        """
        # Check retry count
        if error_context.retry_count >= action.max_attempts:
            return False
        
        # Check custom conditions
        for condition, value in action.conditions.items():
            if condition == "max_error_count":
                error_key = f"{error_context.category.value}:{type(error_context.error).__name__}"
                if self.error_counts[error_key] > value:
                    return False
            elif condition == "severity_threshold":
                if error_context.severity.value > value:
                    return False
        
        return True
    
    def _is_circuit_breaker_open(
        self,
        agent_name: Optional[str],
        category: ErrorCategory
    ) -> bool:
        """
        Check if circuit breaker is open for an agent/category combination.
        
        Args:
            agent_name: Name of the agent
            category: Error category
            
        Returns:
            True if circuit breaker is open
        """
        if not agent_name:
            return False
        
        breaker_key = f"{agent_name}:{category.value}"
        breaker = self.circuit_breakers.get(breaker_key)
        
        if not breaker:
            return False
        
        # Check if breaker should be reset
        if breaker['state'] == 'open':
            time_since_open = (datetime.now() - breaker['opened_at']).total_seconds()
            if time_since_open > breaker.get('timeout', 60):
                breaker['state'] = 'half_open'
                logger.info(f"Circuit breaker half-open: {breaker_key}")
        
        return breaker['state'] == 'open'
    
    def _update_circuit_breaker(
        self,
        agent_name: Optional[str],
        category: ErrorCategory,
        success: bool
    ) -> None:
        """
        Update circuit breaker state based on operation result.
        
        Args:
            agent_name: Name of the agent
            category: Error category
            success: Whether the operation was successful
        """
        if not agent_name:
            return
        
        breaker_key = f"{agent_name}:{category.value}"
        breaker = self.circuit_breakers.setdefault(breaker_key, {
            'state': 'closed',
            'failure_count': 0,
            'success_count': 0,
            'threshold': 5,
            'timeout': 60
        })
        
        if success:
            breaker['success_count'] += 1
            breaker['failure_count'] = 0
            
            if breaker['state'] == 'half_open':
                breaker['state'] = 'closed'
                logger.info(f"Circuit breaker closed: {breaker_key}")
        else:
            breaker['failure_count'] += 1
            breaker['success_count'] = 0
            
            if breaker['failure_count'] >= breaker['threshold']:
                breaker['state'] = 'open'
                breaker['opened_at'] = datetime.now()
                logger.warning(f"Circuit breaker opened: {breaker_key}")
    
    # Recovery action implementations
    async def _retry_with_backoff(self, error_context: ErrorContext) -> bool:
        """Retry with exponential backoff."""
        delay = 2 ** error_context.retry_count
        await asyncio.sleep(delay)
        error_context.retry_count += 1
        return True  # Indicates retry should be attempted
    
    async def _retry_with_timeout_increase(self, error_context: ErrorContext) -> bool:
        """Retry with increased timeout."""
        # This would be implemented by the calling code
        error_context.metadata['timeout_multiplier'] = 2
        error_context.retry_count += 1
        return True
    
    async def _retry_after_resource_wait(self, error_context: ErrorContext) -> bool:
        """Wait for resources and retry."""
        await asyncio.sleep(5)  # Wait for resources to become available
        error_context.retry_count += 1
        return True
    
    async def _restart_agent(self, error_context: ErrorContext) -> bool:
        """Restart the agent."""
        # This would trigger agent restart in the orchestrator
        logger.info(f"Requesting agent restart: {error_context.agent_name}")
        error_context.metadata['restart_requested'] = True
        return True
    
    async def _use_fallback_validation(self, error_context: ErrorContext) -> bool:
        """Use fallback validation method."""
        error_context.metadata['use_fallback'] = True
        return True
    
    async def _escalate_error(self, error_context: ErrorContext) -> bool:
        """Escalate error to human intervention."""
        logger.critical(f"Escalating error: {error_context.error}")
        error_context.metadata['escalated'] = True
        return False  # Indicates manual intervention required
    
    # Recovery strategy handlers
    async def _handle_retry(self, error_context: ErrorContext) -> bool:
        """Handle retry strategy."""
        return True  # Let the caller retry
    
    async def _handle_fallback(self, error_context: ErrorContext) -> bool:
        """Handle fallback strategy."""
        return True  # Use fallback method
    
    async def _handle_skip(self, error_context: ErrorContext) -> bool:
        """Handle skip strategy."""
        logger.info(f"Skipping failed task: {error_context.task_id}")
        return True  # Skip the task
    
    async def _handle_abort(self, error_context: ErrorContext) -> bool:
        """Handle abort strategy."""
        logger.error(f"Aborting due to error: {error_context.error}")
        return False  # Abort the operation
    
    async def _handle_escalate(self, error_context: ErrorContext) -> bool:
        """Handle escalate strategy."""
        return await self._escalate_error(error_context)
    
    async def _handle_restart(self, error_context: ErrorContext) -> bool:
        """Handle restart strategy."""
        return await self._restart_agent(error_context)
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get error statistics.
        
        Returns:
            Dictionary containing error statistics
        """
        total_errors = len(self.error_history)
        
        if total_errors == 0:
            return {"total_errors": 0}
        
        # Count by category
        category_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        
        for error_context in self.error_history:
            category_counts[error_context.category.value] += 1
            severity_counts[error_context.severity.value] += 1
        
        # Recent errors (last hour)
        recent_cutoff = datetime.now() - timedelta(hours=1)
        recent_errors = [
            e for e in self.error_history
            if e.timestamp > recent_cutoff
        ]
        
        return {
            "total_errors": total_errors,
            "recent_errors": len(recent_errors),
            "category_breakdown": dict(category_counts),
            "severity_breakdown": dict(severity_counts),
            "error_rate": len(recent_errors) / 60,  # errors per minute
            "circuit_breakers": {
                k: v['state'] for k, v in self.circuit_breakers.items()
            }
        }
    
    def register_recovery_action(
        self,
        category: ErrorCategory,
        action: RecoveryAction
    ) -> None:
        """
        Register a custom recovery action.
        
        Args:
            category: Error category
            action: Recovery action to register
        """
        self.recovery_actions[category].append(action)
        logger.info(f"Registered recovery action for category: {category.value}")
    
    def clear_error_history(self, older_than_hours: int = 24) -> int:
        """
        Clear old error history.
        
        Args:
            older_than_hours: Clear errors older than this many hours
            
        Returns:
            Number of errors cleared
        """
        cutoff = datetime.now() - timedelta(hours=older_than_hours)
        
        old_count = len(self.error_history)
        self.error_history = [
            e for e in self.error_history
            if e.timestamp > cutoff
        ]
        
        cleared_count = old_count - len(self.error_history)
        logger.info(f"Cleared {cleared_count} old error records")
        
        return cleared_count