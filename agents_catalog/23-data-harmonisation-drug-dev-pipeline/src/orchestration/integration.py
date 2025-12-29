"""
Integration module that ties together all orchestration components.

This module provides a unified interface for initializing and managing
the complete multi-agent orchestration system with Strands framework,
error handling, monitoring, and communication.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from strands import Agent

from .strands_orchestrator import PipelineOrchestrator
from .communication import AgentCommunicationManager
from .workflow_engine import WorkflowEngine, WorkflowConfig
from .error_handler import ErrorHandler
from .monitoring import CentralizedMonitor
from ..models.pipeline import WorkflowState, PipelineTask
from ..utils.logging import get_logger

logger = get_logger(__name__)


class IntegratedOrchestrationSystem:
    """
    Integrated orchestration system that combines all components with Strands framework.
    
    This class provides a unified interface for managing the complete
    multi-agent system with comprehensive error handling, monitoring,
    and communication capabilities using Strands orchestration patterns.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the integrated orchestration system.
        
        Args:
            config: Configuration dictionary containing settings for all components
        """
        self.config = config
        
        # Initialize core components
        self.communication_manager = AgentCommunicationManager(
            config.get("communication", {})
        )
        
        self.workflow_engine = WorkflowEngine(
            WorkflowConfig(**config.get("workflow", {}))
        )
        
        self.error_handler = ErrorHandler(
            config.get("error_handling", {})
        )
        
        self.monitor = CentralizedMonitor(
            config.get("monitoring", {})
        )
        
        self.orchestrator = PipelineOrchestrator(
            config.get("orchestrator", {})
        )
        
        # Integration state
        self._running = False
        self._integration_tasks: List[asyncio.Task] = []
        
        # Set up integrations
        self._setup_integrations()
        
        logger.info("Integrated Strands orchestration system initialized")
    
    def _setup_integrations(self) -> None:
        """Set up integrations between components using Strands framework."""
        
        # Register error handler with workflow engine
        self.workflow_engine.register_workflow_handler(
            "failed", self._handle_workflow_failure
        )
        
        # Register monitoring handlers
        self.workflow_engine.register_workflow_handler(
            "started", self._handle_workflow_started
        )
        
        self.workflow_engine.register_workflow_handler(
            "completed", self._handle_workflow_completed
        )
        
        # Register Strands agents with communication manager (sync part)
        for agent_type, agent in self.orchestrator.agents.items():
            self.communication_manager.register_agent(agent_type.value, agent)
        
        logger.info("Strands component integrations configured")
    
    async def _setup_strands_communication(self) -> None:
        """Set up async communication patterns between Strands agents."""
        
        # Set up Swarm communication if configured
        if self.config.get("orchestrator", {}).get("execution_mode") == "swarm":
            await self._setup_swarm_communication()
        else:
            # Set up Graph communication by default
            await self._setup_graph_communication()
        
        # Set up health monitoring for Strands agents
        async def health_update_handler(message):
            agent_name = message.sender
            health_data = message.payload.get("health_data", {})
            await self.monitor.update_agent_health(agent_name, health_data)
        
        self.communication_manager.register_handler(
            "system", "health_update", health_update_handler
        )
        
        # Set up error reporting for Strands agents
        async def error_report_handler(message):
            agent_name = message.sender
            error_data = message.payload
            
            await self.error_handler.handle_error(
                error=Exception(error_data.get("error_message", "Unknown error")),
                task_id=error_data.get("task_id"),
                agent_name=agent_name,
                metadata=error_data.get("metadata", {})
            )
        
        self.communication_manager.register_handler(
            "system", "error_report", error_report_handler
        )
    
    async def _setup_swarm_communication(self) -> None:
        """Set up Swarm-based communication between Strands agents."""
        try:
            agents = list(self.orchestrator.agents.values())
            await self.communication_manager.setup_swarm_communication(agents)
            logger.info("Swarm communication setup completed")
        except Exception as e:
            logger.error(f"Failed to setup Swarm communication: {e}")
    
    async def _setup_graph_communication(self) -> None:
        """Set up Graph-based communication between Strands agents."""
        try:
            agents = {
                agent_type.value: agent 
                for agent_type, agent in self.orchestrator.agents.items()
            }
            
            # Define dependencies: web_scraper -> data_harmonizer -> quality_assurance
            dependencies = [
                ("web_scraper", "data_harmonizer"),
                ("data_harmonizer", "quality_assurance")
            ]
            
            await self.communication_manager.setup_graph_communication(agents, dependencies)
            logger.info("Graph communication setup completed")
        except Exception as e:
            logger.error(f"Failed to setup Graph communication: {e}")
    
    async def start(self) -> None:
        """Start the integrated Strands orchestration system."""
        if self._running:
            return
        
        logger.info("Starting integrated Strands orchestration system")
        
        try:
            # Start all components
            await self.communication_manager.start()
            await self.workflow_engine.start()
            await self.monitor.start()
            
            # Set up async communication patterns
            await self._setup_strands_communication()
            
            # Start integration tasks
            self._integration_tasks = [
                asyncio.create_task(self._health_monitor_integration()),
                asyncio.create_task(self._error_monitor_integration()),
                asyncio.create_task(self._strands_metrics_integration())
            ]
            
            self._running = True
            logger.info("Integrated Strands orchestration system started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start Strands orchestration system: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop the integrated Strands orchestration system."""
        if not self._running:
            return
        
        logger.info("Stopping integrated Strands orchestration system")
        
        self._running = False
        
        # Cancel integration tasks
        for task in self._integration_tasks:
            task.cancel()
        
        await asyncio.gather(*self._integration_tasks, return_exceptions=True)
        
        # Stop all components
        await self.workflow_engine.stop()
        await self.communication_manager.stop()
        await self.monitor.stop()
        
        # Shutdown orchestrator
        await self.orchestrator.shutdown()
        
        logger.info("Integrated Strands orchestration system stopped")
    
    async def execute_pipeline(self, sources: List[str]) -> Dict[str, Any]:
        """
        Execute the complete pharmaceutical data pipeline using Strands orchestration.
        
        Args:
            sources: List of pharmaceutical company URLs to process
            
        Returns:
            Pipeline execution results
        """
        if not self._running:
            raise RuntimeError("Strands orchestration system is not running")
        
        logger.info(f"Executing Strands pipeline for {len(sources)} sources")
        
        try:
            # Use the Strands orchestrator to execute the pipeline
            result = await self.orchestrator.execute_pipeline(sources)
            
            # Record successful execution
            self.monitor.record_pipeline_execution(
                sources=sources,
                execution_time=result.get("execution_summary", {}).get("execution_time_ms", 0),
                status="success"
            )
            
            logger.info("Strands pipeline execution completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Strands pipeline execution failed: {e}")
            
            # Record failed execution
            self.monitor.record_pipeline_execution(
                sources=sources,
                execution_time=0,
                status="failed"
            )
            
            # Handle the error through error handler
            await self.error_handler.handle_error(
                error=e,
                metadata={"sources": sources, "operation": "strands_pipeline_execution"}
            )
            
            raise
    
    async def execute_pipeline_with_swarm(self, sources: List[str]) -> Dict[str, Any]:
        """
        Execute pipeline using Strands Swarm pattern.
        
        Args:
            sources: List of pharmaceutical company URLs to process
            
        Returns:
            Swarm execution results
        """
        if not self._running:
            raise RuntimeError("Strands orchestration system is not running")
        
        task_description = f"""
        Collect and process pharmaceutical pipeline data from these sources: {', '.join(sources)}
        
        Collaborate as a team to:
        1. Collect data from each source with robots.txt compliance
        2. Harmonize and standardize the collected data using biomedical ontologies
        3. Perform comprehensive quality assessment and generate reports
        
        Ensure all data meets quality standards and is properly validated.
        """
        
        try:
            result = await self.communication_manager.send_message_via_swarm(
                task_description=task_description,
                invocation_state={"sources": sources, "pipeline_id": f"swarm_{datetime.now().isoformat()}"}
            )
            
            logger.info("Swarm pipeline execution completed")
            return {"swarm_result": result, "sources": sources}
            
        except Exception as e:
            logger.error(f"Swarm pipeline execution failed: {e}")
            raise
    
    async def execute_pipeline_with_graph(self, sources: List[str]) -> Dict[str, Any]:
        """
        Execute pipeline using Strands Graph pattern.
        
        Args:
            sources: List of pharmaceutical company URLs to process
            
        Returns:
            Graph execution results
        """
        if not self._running:
            raise RuntimeError("Strands orchestration system is not running")
        
        task_description = f"""
        Process pharmaceutical pipeline data from these sources: {', '.join(sources)}
        
        Follow this structured workflow:
        1. Web Scraper: Collect data from all sources with compliance checks
        2. Data Harmonizer: Standardize and enrich the collected data
        3. Quality Assurance: Perform comprehensive quality assessment
        
        Each step must be completed before proceeding to the next.
        """
        
        try:
            result = await self.communication_manager.send_message_via_graph(
                task_description=task_description,
                invocation_state={"sources": sources, "pipeline_id": f"graph_{datetime.now().isoformat()}"}
            )
            
            logger.info("Graph pipeline execution completed")
            return {"graph_result": result, "sources": sources}
            
        except Exception as e:
            logger.error(f"Graph pipeline execution failed: {e}")
            raise
    
    async def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive Strands system status.
        
        Returns:
            System status dictionary
        """
        status = {
            "running": self._running,
            "timestamp": datetime.now().isoformat(),
            "framework": "Strands Agents SDK",
            "components": {
                "communication_manager": "running" if self._running else "stopped",
                "workflow_engine": "running" if self._running else "stopped",
                "error_handler": "initialized",
                "monitor": "running" if self._running else "stopped",
                "strands_orchestrator": "initialized"
            },
            "strands_agents": {},
            "orchestration_patterns": {
                "swarm": "available" if self.orchestrator.swarm else "not_configured",
                "graph": "available" if self.orchestrator.graph else "not_configured"
            },
            "metrics": {},
            "alerts": {},
            "errors": {}
        }
        
        if self._running:
            # Get Strands agent health
            agent_health = self.communication_manager.get_all_agent_health()
            status["strands_agents"] = {
                name: {
                    "status": health.status,
                    "is_healthy": health.is_healthy,
                    "success_rate": health.success_rate,
                    "active_tasks": health.active_tasks,
                    "last_heartbeat": health.last_heartbeat.isoformat()
                }
                for name, health in agent_health.items()
            }
            
            # Get communication metrics
            comm_metrics = self.communication_manager.get_communication_metrics()
            status["communication_metrics"] = comm_metrics
            
            # Get metrics summary
            status["metrics"] = self.monitor.get_metrics_summary(time_window_minutes=60)
            
            # Get alert summary
            status["alerts"] = {
                "total": len(self.monitor.alerts),
                "unresolved": len([a for a in self.monitor.alerts.values() if not a.resolved]),
                "recent": len([
                    a for a in self.monitor.alerts.values()
                    if (datetime.now() - a.timestamp).total_seconds() < 3600
                ])
            }
            
            # Get error statistics
            status["errors"] = self.error_handler.get_error_statistics()
        
        return status
    
    # Event handlers for component integration
    
    async def _handle_workflow_started(self, workflow: WorkflowState) -> None:
        """Handle workflow started event."""
        self.monitor.record_workflow_start(workflow)
        
        # Notify via communication manager
        await self.communication_manager.broadcast(
            sender="orchestrator",
            message_type="workflow_started",
            payload={"workflow_id": workflow.id, "total_tasks": len(workflow.plan)}
        )
    
    async def _handle_workflow_completed(self, workflow: WorkflowState) -> None:
        """Handle workflow completed event."""
        self.monitor.record_workflow_completion(workflow)
        
        # Notify via communication manager
        await self.communication_manager.broadcast(
            sender="orchestrator",
            message_type="workflow_completed",
            payload={
                "workflow_id": workflow.id,
                "status": workflow.status.value,
                "duration": workflow.duration,
                "completed_tasks": len(workflow.completed_tasks),
                "failed_tasks": len(workflow.failed_tasks)
            }
        )
    
    async def _handle_workflow_failure(self, workflow: WorkflowState) -> None:
        """Handle workflow failure event."""
        # Create alert for workflow failure
        self.monitor.create_alert(
            level=self.monitor.AlertLevel.ERROR,
            title=f"Strands Workflow Failed: {workflow.id}",
            message=f"Strands workflow {workflow.id} failed: {workflow.error}",
            source="strands_workflow_engine",
            metadata={
                "workflow_id": workflow.id,
                "failed_tasks": len(workflow.failed_tasks),
                "error": workflow.error
            }
        )
    
    # Background integration tasks
    
    async def _health_monitor_integration(self) -> None:
        """Background task to integrate Strands agent health monitoring."""
        while self._running:
            try:
                # Check Strands agent health and create alerts if needed
                agent_health = self.communication_manager.get_all_agent_health()
                
                for agent_name, health in agent_health.items():
                    if not health.is_healthy:
                        self.monitor.create_alert(
                            level=self.monitor.AlertLevel.WARNING,
                            title=f"Strands Agent Health Issue: {agent_name}",
                            message=f"Strands agent {agent_name} is reporting unhealthy status",
                            source=f"strands_agent_{agent_name}",
                            metadata={"health_data": health.__dict__}
                        )
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in Strands health monitor integration: {e}")
                await asyncio.sleep(60)
    
    async def _error_monitor_integration(self) -> None:
        """Background task to integrate error monitoring."""
        while self._running:
            try:
                # Get error statistics and create alerts for high error rates
                error_stats = self.error_handler.get_error_statistics()
                
                if error_stats.get("error_rate", 0) > 5:  # More than 5 errors per minute
                    self.monitor.create_alert(
                        level=self.monitor.AlertLevel.ERROR,
                        title="High Error Rate Detected",
                        message=f"Error rate is {error_stats['error_rate']:.1f} errors/minute",
                        source="error_handler",
                        metadata=error_stats
                    )
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in error monitor integration: {e}")
                await asyncio.sleep(300)
    
    async def _strands_metrics_integration(self) -> None:
        """Background task to integrate Strands-specific metrics."""
        while self._running:
            try:
                # Collect Strands orchestration metrics
                orchestrator_metrics = self.orchestrator.metrics_collector.get_pipeline_metrics()
                
                # Record metrics in monitor
                for metric_name, metric_value in orchestrator_metrics.items():
                    if isinstance(metric_value, (int, float)):
                        self.monitor.record_metric(f"strands_{metric_name}", metric_value)
                
                # Collect communication metrics
                comm_metrics = self.communication_manager.get_communication_metrics()
                
                # Record communication metrics
                for metric_category, metrics in comm_metrics.items():
                    if isinstance(metrics, dict):
                        for metric_name, metric_value in metrics.items():
                            if isinstance(metric_value, (int, float)):
                                self.monitor.record_metric(f"comm_{metric_category}_{metric_name}", metric_value)
                
                await asyncio.sleep(120)  # Collect every 2 minutes
                
            except Exception as e:
                logger.error(f"Error in Strands metrics integration: {e}")
                await asyncio.sleep(120)