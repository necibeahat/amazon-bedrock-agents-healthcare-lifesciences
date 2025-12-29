"""
Workflow coordination engine for managing task sequencing and dependencies.

This module implements the workflow engine that coordinates the execution
of pipeline tasks according to their dependencies and priorities.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque

from ..models.pipeline import PipelineTask, TaskStatus, WorkflowState, WorkflowMetrics
from ..utils.logging import get_logger

logger = get_logger(__name__)


class WorkflowStrategy(Enum):
    """Workflow execution strategies."""
    SEQUENTIAL = "sequential"  # Execute tasks one by one
    PARALLEL = "parallel"     # Execute independent tasks in parallel
    PRIORITY = "priority"     # Execute by priority order
    DEPENDENCY = "dependency" # Execute based on dependency resolution


class ExecutionMode(Enum):
    """Execution modes for workflow."""
    NORMAL = "normal"         # Normal execution
    FAST_FAIL = "fast_fail"   # Stop on first failure
    CONTINUE = "continue"     # Continue despite failures
    RETRY = "retry"          # Retry failed tasks


@dataclass
class WorkflowConfig:
    """
    Configuration for workflow execution.
    
    Attributes:
        strategy: Execution strategy
        mode: Execution mode
        max_concurrent_tasks: Maximum number of concurrent tasks
        task_timeout: Default task timeout in seconds
        retry_attempts: Number of retry attempts for failed tasks
        retry_delay: Delay between retry attempts in seconds
        enable_checkpoints: Whether to enable workflow checkpoints
        checkpoint_interval: Interval between checkpoints in seconds
    """
    strategy: WorkflowStrategy = WorkflowStrategy.DEPENDENCY
    mode: ExecutionMode = ExecutionMode.NORMAL
    max_concurrent_tasks: int = 5
    task_timeout: int = 300  # 5 minutes
    retry_attempts: int = 3
    retry_delay: int = 5
    enable_checkpoints: bool = True
    checkpoint_interval: int = 60  # 1 minute


@dataclass
class TaskExecution:
    """
    Tracks the execution state of a task.
    
    Attributes:
        task: The pipeline task
        attempts: Number of execution attempts
        last_attempt: Timestamp of last attempt
        execution_future: Future for current execution
        retry_count: Current retry count
    """
    task: PipelineTask
    attempts: int = 0
    last_attempt: Optional[datetime] = None
    execution_future: Optional[asyncio.Future] = None
    retry_count: int = 0


class WorkflowEngine:
    """
    Coordinates the execution of pipeline workflows with dependency management,
    parallel execution, error handling, and retry mechanisms.
    """
    
    def __init__(self, config: WorkflowConfig = None):
        """
        Initialize the workflow engine.
        
        Args:
            config: Workflow configuration
        """
        self.config = config or WorkflowConfig()
        
        # Execution tracking
        self.active_workflows: Dict[str, WorkflowState] = {}
        self.task_executions: Dict[str, TaskExecution] = {}
        self.execution_semaphore = asyncio.Semaphore(self.config.max_concurrent_tasks)
        
        # Event handlers
        self.task_handlers: Dict[str, Callable] = {}
        self.workflow_handlers: Dict[str, Callable] = {}
        
        # Background tasks
        self._background_tasks: List[asyncio.Task] = []
        self._running = False
        
        logger.info(f"Workflow engine initialized with strategy: {self.config.strategy.value}")
    
    async def start(self) -> None:
        """Start the workflow engine."""
        if self._running:
            return
        
        self._running = True
        
        # Start background tasks
        if self.config.enable_checkpoints:
            self._background_tasks.append(
                asyncio.create_task(self._checkpoint_monitor())
            )
        
        self._background_tasks.append(
            asyncio.create_task(self._retry_monitor())
        )
        
        logger.info("Workflow engine started")
    
    async def stop(self) -> None:
        """Stop the workflow engine."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel all active workflows
        for workflow_id in list(self.active_workflows.keys()):
            await self.cancel_workflow(workflow_id)
        
        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()
        
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        logger.info("Workflow engine stopped")
    
    def register_task_handler(self, action: str, handler: Callable) -> None:
        """
        Register a handler for a specific task action.
        
        Args:
            action: Task action name
            handler: Handler function
        """
        self.task_handlers[action] = handler
        logger.debug(f"Registered task handler for action: {action}")
    
    def register_workflow_handler(self, event: str, handler: Callable) -> None:
        """
        Register a handler for workflow events.
        
        Args:
            event: Event name (started, completed, failed, etc.)
            handler: Handler function
        """
        self.workflow_handlers[event] = handler
        logger.debug(f"Registered workflow handler for event: {event}")
    
    async def execute_workflow(self, workflow: WorkflowState) -> WorkflowState:
        """
        Execute a complete workflow.
        
        Args:
            workflow: Workflow to execute
            
        Returns:
            Updated workflow state
        """
        logger.info(f"Starting workflow execution: {workflow.id}")
        
        # Register workflow
        self.active_workflows[workflow.id] = workflow
        workflow.status = TaskStatus.RUNNING
        workflow.start_time = datetime.now()
        
        # Initialize task executions
        for task in workflow.plan:
            self.task_executions[task.id] = TaskExecution(task=task)
        
        try:
            # Notify workflow started
            await self._notify_workflow_event("started", workflow)
            
            # Execute based on strategy
            if self.config.strategy == WorkflowStrategy.SEQUENTIAL:
                await self._execute_sequential(workflow)
            elif self.config.strategy == WorkflowStrategy.PARALLEL:
                await self._execute_parallel(workflow)
            elif self.config.strategy == WorkflowStrategy.PRIORITY:
                await self._execute_priority(workflow)
            else:  # DEPENDENCY
                await self._execute_dependency(workflow)
            
            # Check final status
            failed_tasks = [t for t in workflow.plan if t.status == TaskStatus.FAILED]
            
            if failed_tasks and self.config.mode == ExecutionMode.FAST_FAIL:
                workflow.status = TaskStatus.FAILED
                workflow.error = f"Workflow failed due to {len(failed_tasks)} failed tasks"
            elif all(t.status == TaskStatus.COMPLETED for t in workflow.plan):
                workflow.status = TaskStatus.COMPLETED
            else:
                workflow.status = TaskStatus.FAILED
                workflow.error = f"Workflow incomplete: {len(failed_tasks)} failed tasks"
            
            workflow.end_time = datetime.now()
            
            # Notify workflow completed/failed
            event = "completed" if workflow.status == TaskStatus.COMPLETED else "failed"
            await self._notify_workflow_event(event, workflow)
            
            logger.info(f"Workflow {workflow.id} {event}")
            
        except Exception as e:
            workflow.status = TaskStatus.FAILED
            workflow.error = str(e)
            workflow.end_time = datetime.now()
            
            await self._notify_workflow_event("failed", workflow)
            logger.error(f"Workflow {workflow.id} failed: {e}")
            
        finally:
            # Clean up
            self.active_workflows.pop(workflow.id, None)
            for task in workflow.plan:
                self.task_executions.pop(task.id, None)
        
        return workflow
    
    async def cancel_workflow(self, workflow_id: str) -> bool:
        """
        Cancel a running workflow.
        
        Args:
            workflow_id: ID of workflow to cancel
            
        Returns:
            True if workflow was cancelled, False if not found
        """
        workflow = self.active_workflows.get(workflow_id)
        if not workflow:
            return False
        
        logger.info(f"Cancelling workflow: {workflow_id}")
        
        # Cancel all running tasks
        for task in workflow.plan:
            if task.status == TaskStatus.RUNNING:
                execution = self.task_executions.get(task.id)
                if execution and execution.execution_future:
                    execution.execution_future.cancel()
                task.status = TaskStatus.CANCELLED
        
        workflow.status = TaskStatus.CANCELLED
        workflow.end_time = datetime.now()
        
        await self._notify_workflow_event("cancelled", workflow)
        
        return True
    
    async def _execute_sequential(self, workflow: WorkflowState) -> None:
        """Execute tasks sequentially."""
        for task in sorted(workflow.plan, key=lambda t: t.priority):
            if workflow.status == TaskStatus.CANCELLED:
                break
            
            await self._execute_task(task)
            
            if task.status == TaskStatus.FAILED and self.config.mode == ExecutionMode.FAST_FAIL:
                break
    
    async def _execute_parallel(self, workflow: WorkflowState) -> None:
        """Execute all tasks in parallel (ignoring dependencies)."""
        tasks = [self._execute_task(task) for task in workflow.plan]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _execute_priority(self, workflow: WorkflowState) -> None:
        """Execute tasks by priority order."""
        # Group tasks by priority
        priority_groups = defaultdict(list)
        for task in workflow.plan:
            priority_groups[task.priority].append(task)
        
        # Execute each priority group
        for priority in sorted(priority_groups.keys()):
            if workflow.status == TaskStatus.CANCELLED:
                break
            
            # Execute tasks in this priority group in parallel
            tasks = [self._execute_task(task) for task in priority_groups[priority]]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check for failures
            failed_tasks = [t for t in priority_groups[priority] if t.status == TaskStatus.FAILED]
            if failed_tasks and self.config.mode == ExecutionMode.FAST_FAIL:
                break
    
    async def _execute_dependency(self, workflow: WorkflowState) -> None:
        """Execute tasks based on dependency resolution."""
        completed_tasks = set()
        remaining_tasks = set(task.id for task in workflow.plan)
        
        while remaining_tasks and workflow.status != TaskStatus.CANCELLED:
            # Find tasks ready to execute
            ready_tasks = []
            for task in workflow.plan:
                if (task.id in remaining_tasks and
                    task.status == TaskStatus.PENDING and
                    all(dep in completed_tasks for dep in task.dependencies)):
                    ready_tasks.append(task)
            
            if not ready_tasks:
                # Check if we're stuck due to failed dependencies
                failed_tasks = [t for t in workflow.plan if t.status == TaskStatus.FAILED]
                if failed_tasks:
                    logger.error(f"Workflow blocked by failed tasks: {[t.id for t in failed_tasks]}")
                    break
                
                # Wait a bit and try again
                await asyncio.sleep(0.1)
                continue
            
            # Execute ready tasks in parallel (up to concurrency limit)
            execution_tasks = []
            for task in ready_tasks[:self.config.max_concurrent_tasks]:
                execution_tasks.append(self._execute_task(task))
            
            # Wait for this batch to complete
            await asyncio.gather(*execution_tasks, return_exceptions=True)
            
            # Update completed tasks
            for task in ready_tasks:
                if task.status == TaskStatus.COMPLETED:
                    completed_tasks.add(task.id)
                    remaining_tasks.discard(task.id)
                elif task.status == TaskStatus.FAILED:
                    remaining_tasks.discard(task.id)
                    if self.config.mode == ExecutionMode.FAST_FAIL:
                        return
    
    async def _execute_task(self, task: PipelineTask) -> None:
        """
        Execute a single task with retry logic.
        
        Args:
            task: Task to execute
        """
        execution = self.task_executions[task.id]
        
        async with self.execution_semaphore:
            for attempt in range(self.config.retry_attempts + 1):
                if task.status == TaskStatus.CANCELLED:
                    break
                
                try:
                    task.status = TaskStatus.RUNNING
                    task.start_time = datetime.now()
                    execution.attempts += 1
                    execution.last_attempt = datetime.now()
                    
                    logger.debug(f"Executing task {task.id} (attempt {attempt + 1})")
                    
                    # Get task handler
                    handler = self.task_handlers.get(task.action)
                    if not handler:
                        raise ValueError(f"No handler found for action: {task.action}")
                    
                    # Execute task with timeout
                    execution.execution_future = asyncio.create_task(
                        handler(task)
                    )
                    
                    result = await asyncio.wait_for(
                        execution.execution_future,
                        timeout=self.config.task_timeout
                    )
                    
                    # Task completed successfully
                    task.status = TaskStatus.COMPLETED
                    task.end_time = datetime.now()
                    task.result = result
                    
                    logger.info(f"Task {task.id} completed successfully")
                    break
                    
                except asyncio.CancelledError:
                    task.status = TaskStatus.CANCELLED
                    logger.info(f"Task {task.id} was cancelled")
                    break
                    
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Task {task.id} failed (attempt {attempt + 1}): {error_msg}")
                    
                    if attempt < self.config.retry_attempts:
                        # Retry after delay
                        execution.retry_count += 1
                        await asyncio.sleep(self.config.retry_delay)
                        continue
                    else:
                        # Final failure
                        task.status = TaskStatus.FAILED
                        task.end_time = datetime.now()
                        task.error = error_msg
                        break
                
                finally:
                    execution.execution_future = None
    
    async def _notify_workflow_event(self, event: str, workflow: WorkflowState) -> None:
        """Notify workflow event handlers."""
        handler = self.workflow_handlers.get(event)
        if handler:
            try:
                await handler(workflow)
            except Exception as e:
                logger.error(f"Error in workflow event handler for {event}: {e}")
    
    async def _checkpoint_monitor(self) -> None:
        """Background task to create workflow checkpoints."""
        while self._running:
            try:
                for workflow in self.active_workflows.values():
                    if workflow.status == TaskStatus.RUNNING:
                        await self._create_checkpoint(workflow)
                
                await asyncio.sleep(self.config.checkpoint_interval)
                
            except Exception as e:
                logger.error(f"Error in checkpoint monitor: {e}")
                await asyncio.sleep(self.config.checkpoint_interval)
    
    async def _retry_monitor(self) -> None:
        """Background task to monitor and retry failed tasks."""
        while self._running:
            try:
                current_time = datetime.now()
                
                for execution in self.task_executions.values():
                    task = execution.task
                    
                    # Check for tasks that need retry
                    if (task.status == TaskStatus.FAILED and
                        execution.retry_count < self.config.retry_attempts and
                        execution.last_attempt and
                        (current_time - execution.last_attempt).total_seconds() >= self.config.retry_delay):
                        
                        logger.info(f"Retrying failed task: {task.id}")
                        task.status = TaskStatus.PENDING
                        task.error = None
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in retry monitor: {e}")
                await asyncio.sleep(10)
    
    async def _create_checkpoint(self, workflow: WorkflowState) -> None:
        """Create a checkpoint for the workflow."""
        checkpoint_data = {
            "workflow_id": workflow.id,
            "timestamp": datetime.now().isoformat(),
            "status": workflow.status.value,
            "completed_tasks": [t.id for t in workflow.plan if t.status == TaskStatus.COMPLETED],
            "failed_tasks": [t.id for t in workflow.plan if t.status == TaskStatus.FAILED],
            "running_tasks": [t.id for t in workflow.plan if t.status == TaskStatus.RUNNING]
        }
        
        logger.debug(f"Created checkpoint for workflow {workflow.id}")
        # In a real implementation, this would be saved to persistent storage
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a workflow.
        
        Args:
            workflow_id: ID of the workflow
            
        Returns:
            Workflow status dictionary or None if not found
        """
        workflow = self.active_workflows.get(workflow_id)
        if not workflow:
            return None
        
        return {
            "id": workflow.id,
            "status": workflow.status.value,
            "start_time": workflow.start_time.isoformat() if workflow.start_time else None,
            "end_time": workflow.end_time.isoformat() if workflow.end_time else None,
            "progress": workflow.progress_percentage,
            "total_tasks": len(workflow.plan),
            "completed_tasks": len(workflow.completed_tasks),
            "failed_tasks": len(workflow.failed_tasks),
            "running_tasks": len(workflow.running_tasks),
            "error": workflow.error
        }
    
    def get_workflow_metrics(self, workflow_id: str) -> Optional[WorkflowMetrics]:
        """
        Get metrics for a workflow.
        
        Args:
            workflow_id: ID of the workflow
            
        Returns:
            Workflow metrics or None if not found
        """
        workflow = self.active_workflows.get(workflow_id)
        if not workflow:
            return None
        
        return WorkflowMetrics.from_workflow(workflow)