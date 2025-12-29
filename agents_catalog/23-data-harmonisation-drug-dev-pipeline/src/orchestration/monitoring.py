"""
Centralized monitoring and logging system for multi-agent orchestration.

This module implements comprehensive monitoring, metrics collection,
and logging for all agents in the pharmaceutical pipeline system.
"""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque

# Optional imports - will use mock implementations if not available
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    from opentelemetry import trace, metrics
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False

from ..models.pipeline import WorkflowState, PipelineTask, TaskStatus, AgentHealth
from ..utils.logging import get_logger

logger = get_logger(__name__)


class MetricType(Enum):
    """Types of metrics collected."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class MetricPoint:
    """
    A single metric data point.
    
    Attributes:
        name: Metric name
        value: Metric value
        timestamp: When the metric was recorded
        labels: Metric labels/tags
        metric_type: Type of metric
    """
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    labels: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE


@dataclass
class Alert:
    """
    System alert information.
    
    Attributes:
        id: Unique alert identifier
        level: Alert severity level
        title: Alert title
        message: Alert message
        timestamp: When alert was created
        source: Source of the alert
        metadata: Additional alert metadata
        resolved: Whether alert has been resolved
        resolved_at: When alert was resolved
    """
    id: str
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class CentralizedMonitor:
    """
    Centralized monitoring system for multi-agent orchestration.
    
    Provides comprehensive monitoring, metrics collection, alerting,
    and observability for the pharmaceutical pipeline system.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the centralized monitor.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Metrics storage
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.metric_handlers: Dict[str, Callable] = {}
        
        # Alert management
        self.alerts: Dict[str, Alert] = {}
        self.alert_handlers: Dict[AlertLevel, List[Callable]] = defaultdict(list)
        
        # Agent monitoring
        self.agent_metrics: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.agent_health_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Workflow monitoring
        self.workflow_metrics: Dict[str, Dict[str, Any]] = {}
        self.task_metrics: Dict[str, Dict[str, Any]] = {}
        
        # System monitoring
        self.system_metrics: deque = deque(maxlen=1000)
        
        # OpenTelemetry setup (if available)
        if OTEL_AVAILABLE:
            self._setup_opentelemetry()
        else:
            logger.info("OpenTelemetry not available, using mock implementation")
        
        # Langfuse setup (if available)
        if LANGFUSE_AVAILABLE:
            self._setup_langfuse()
        else:
            logger.info("Langfuse not available, using mock implementation")
            self.langfuse = None
        
        # Background tasks
        self._background_tasks: List[asyncio.Task] = []
        self._running = False
        
        logger.info("Centralized monitor initialized")
    
    def _setup_opentelemetry(self) -> None:
        """Set up OpenTelemetry tracing and metrics."""
        try:
            # Set up tracing
            trace.set_tracer_provider(TracerProvider())
            tracer_provider = trace.get_tracer_provider()
            
            # Add OTLP exporter if configured
            if self.config.get("otlp_endpoint"):
                otlp_exporter = OTLPSpanExporter(
                    endpoint=self.config["otlp_endpoint"],
                    headers=self.config.get("otlp_headers", {})
                )
                span_processor = BatchSpanProcessor(otlp_exporter)
                tracer_provider.add_span_processor(span_processor)
            
            self.tracer = trace.get_tracer(__name__)
            
            # Set up metrics
            metric_reader = PeriodicExportingMetricReader(
                OTLPMetricExporter(
                    endpoint=self.config.get("otlp_metrics_endpoint", self.config.get("otlp_endpoint")),
                    headers=self.config.get("otlp_headers", {})
                ),
                export_interval_millis=30000  # 30 seconds
            )
            
            metrics.set_meter_provider(MeterProvider(metric_readers=[metric_reader]))
            self.meter = metrics.get_meter(__name__)
            
            # Create metric instruments
            self.task_counter = self.meter.create_counter(
                "pipeline_tasks_total",
                description="Total number of pipeline tasks"
            )
            
            self.task_duration = self.meter.create_histogram(
                "pipeline_task_duration_seconds",
                description="Task execution duration in seconds"
            )
            
            self.agent_health_gauge = self.meter.create_gauge(
                "agent_health_score",
                description="Agent health score (0-100)"
            )
            
            logger.info("OpenTelemetry configured successfully")
            
        except Exception as e:
            logger.warning(f"Failed to configure OpenTelemetry: {e}")
    
    def _setup_langfuse(self) -> None:
        """Set up Langfuse for LLM observability."""
        try:
            if self.config.get("langfuse_public_key") and self.config.get("langfuse_secret_key"):
                self.langfuse = Langfuse(
                    public_key=self.config["langfuse_public_key"],
                    secret_key=self.config["langfuse_secret_key"],
                    host=self.config.get("langfuse_host", "https://cloud.langfuse.com")
                )
                logger.info("Langfuse configured successfully")
            else:
                self.langfuse = None
                logger.info("Langfuse not configured (missing credentials)")
                
        except Exception as e:
            logger.warning(f"Failed to configure Langfuse: {e}")
            self.langfuse = None
    
    async def start(self) -> None:
        """Start the monitoring system."""
        if self._running:
            return
        
        self._running = True
        
        # Start background monitoring tasks
        self._background_tasks = [
            asyncio.create_task(self._system_monitor()),
            asyncio.create_task(self._alert_processor()),
            asyncio.create_task(self._metrics_aggregator()),
            asyncio.create_task(self._health_checker())
        ]
        
        logger.info("Centralized monitor started")
    
    async def stop(self) -> None:
        """Stop the monitoring system."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()
        
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # Flush Langfuse if configured
        if self.langfuse:
            self.langfuse.flush()
        
        logger.info("Centralized monitor stopped")
    
    def record_metric(
        self,
        name: str,
        value: float,
        labels: Dict[str, str] = None,
        metric_type: MetricType = MetricType.GAUGE
    ) -> None:
        """
        Record a metric value.
        
        Args:
            name: Metric name
            value: Metric value
            labels: Metric labels
            metric_type: Type of metric
        """
        metric_point = MetricPoint(
            name=name,
            value=value,
            labels=labels or {},
            metric_type=metric_type
        )
        
        self.metrics[name].append(metric_point)
        
        # Call registered handlers
        handler = self.metric_handlers.get(name)
        if handler:
            try:
                handler(metric_point)
            except Exception as e:
                logger.error(f"Error in metric handler for {name}: {e}")
        
        # Record to OpenTelemetry if available
        if OTEL_AVAILABLE:
            self._record_otel_metric(metric_point)
    
    def _record_otel_metric(self, metric_point: MetricPoint) -> None:
        """Record metric to OpenTelemetry."""
        try:
            labels_dict = metric_point.labels
            
            if metric_point.metric_type == MetricType.COUNTER:
                if hasattr(self, 'task_counter'):
                    self.task_counter.add(metric_point.value, labels_dict)
            elif metric_point.metric_type == MetricType.HISTOGRAM:
                if hasattr(self, 'task_duration'):
                    self.task_duration.record(metric_point.value, labels_dict)
            elif metric_point.metric_type == MetricType.GAUGE:
                if hasattr(self, 'agent_health_gauge'):
                    self.agent_health_gauge.set(metric_point.value, labels_dict)
                    
        except Exception as e:
            logger.debug(f"Failed to record OpenTelemetry metric: {e}")
    
    def record_agent_metric(
        self,
        agent_name: str,
        metric_name: str,
        value: Any,
        timestamp: datetime = None
    ) -> None:
        """
        Record an agent-specific metric.
        
        Args:
            agent_name: Name of the agent
            metric_name: Name of the metric
            value: Metric value
            timestamp: Metric timestamp
        """
        timestamp = timestamp or datetime.now()
        
        self.agent_metrics[agent_name][metric_name] = {
            "value": value,
            "timestamp": timestamp
        }
        
        # Record as general metric with agent label
        self.record_metric(
            name=f"agent_{metric_name}",
            value=float(value) if isinstance(value, (int, float)) else 0,
            labels={"agent": agent_name}
        )
    
    def record_workflow_start(self, workflow: WorkflowState) -> None:
        """
        Record workflow start.
        
        Args:
            workflow: Workflow that started
        """
        self.workflow_metrics[workflow.id] = {
            "start_time": workflow.start_time,
            "status": workflow.status.value,
            "total_tasks": len(workflow.plan),
            "agent_distribution": self._get_agent_distribution(workflow.plan)
        }
        
        self.record_metric(
            name="workflow_started",
            value=1,
            labels={"workflow_id": workflow.id},
            metric_type=MetricType.COUNTER
        )
        
        # Create Langfuse trace if configured
        if self.langfuse:
            try:
                self.langfuse.trace(
                    name=f"workflow_{workflow.id}",
                    metadata={
                        "total_tasks": len(workflow.plan),
                        "start_time": workflow.start_time.isoformat()
                    }
                )
            except Exception as e:
                logger.debug(f"Failed to create Langfuse trace: {e}")
    
    def record_workflow_completion(self, workflow: WorkflowState) -> None:
        """
        Record workflow completion.
        
        Args:
            workflow: Workflow that completed
        """
        if workflow.id in self.workflow_metrics:
            metrics = self.workflow_metrics[workflow.id]
            metrics.update({
                "end_time": workflow.end_time,
                "status": workflow.status.value,
                "duration": workflow.duration,
                "completed_tasks": len(workflow.completed_tasks),
                "failed_tasks": len(workflow.failed_tasks)
            })
        
        self.record_metric(
            name="workflow_completed",
            value=1,
            labels={
                "workflow_id": workflow.id,
                "status": workflow.status.value
            },
            metric_type=MetricType.COUNTER
        )
        
        if workflow.duration:
            self.record_metric(
                name="workflow_duration",
                value=workflow.duration,
                labels={"workflow_id": workflow.id},
                metric_type=MetricType.HISTOGRAM
            )
    
    def record_task_execution(
        self,
        task: PipelineTask,
        agent_name: str,
        execution_time: float,
        status: str
    ) -> None:
        """
        Record task execution metrics.
        
        Args:
            task: The executed task
            agent_name: Name of the agent that executed the task
            execution_time: Task execution time in seconds
            status: Task execution status
        """
        self.task_metrics[task.id] = {
            "agent": agent_name,
            "action": task.action,
            "execution_time": execution_time,
            "status": status,
            "timestamp": datetime.now()
        }
        
        # Record metrics
        self.record_metric(
            name="task_executed",
            value=1,
            labels={
                "agent": agent_name,
                "action": task.action,
                "status": status
            },
            metric_type=MetricType.COUNTER
        )
        
        self.record_metric(
            name="task_execution_time",
            value=execution_time,
            labels={
                "agent": agent_name,
                "action": task.action
            },
            metric_type=MetricType.HISTOGRAM
        )
    
    def record_agent_health(self, agent_name: str, health: AgentHealth) -> None:
        """
        Record agent health information.
        
        Args:
            agent_name: Name of the agent
            health: Agent health information
        """
        health_data = {
            "timestamp": health.last_heartbeat,
            "status": health.status,
            "active_tasks": health.active_tasks,
            "success_rate": health.success_rate,
            "memory_usage": health.memory_usage,
            "cpu_usage": health.cpu_usage,
            "is_healthy": health.is_healthy
        }
        
        self.agent_health_history[agent_name].append(health_data)
        
        # Record health metrics
        self.record_metric(
            name="agent_health_score",
            value=health.success_rate,
            labels={"agent": agent_name}
        )
        
        self.record_metric(
            name="agent_memory_usage",
            value=health.memory_usage,
            labels={"agent": agent_name}
        )
        
        self.record_metric(
            name="agent_cpu_usage",
            value=health.cpu_usage,
            labels={"agent": agent_name}
        )
        
        # Check for health alerts
        if not health.is_healthy:
            self.create_alert(
                level=AlertLevel.WARNING,
                title=f"Agent Health Issue: {agent_name}",
                message=f"Agent {agent_name} is reporting unhealthy status",
                source=agent_name,
                metadata={"health_data": health_data}
            )
    
    def create_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        source: str = "system",
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Create a system alert.
        
        Args:
            level: Alert severity level
            title: Alert title
            message: Alert message
            source: Source of the alert
            metadata: Additional alert metadata
            
        Returns:
            Alert ID
        """
        alert_id = f"{source}_{datetime.now().timestamp()}"
        
        alert = Alert(
            id=alert_id,
            level=level,
            title=title,
            message=message,
            source=source,
            metadata=metadata or {}
        )
        
        self.alerts[alert_id] = alert
        
        logger.log(
            logging.CRITICAL if level == AlertLevel.CRITICAL else
            logging.ERROR if level == AlertLevel.ERROR else
            logging.WARNING if level == AlertLevel.WARNING else
            logging.INFO,
            f"Alert created: {title} - {message}"
        )
        
        # Trigger alert handlers
        handlers = self.alert_handlers.get(level, [])
        for handler in handlers:
            try:
                asyncio.create_task(handler(alert))
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")
        
        return alert_id
    
    def resolve_alert(self, alert_id: str) -> bool:
        """
        Resolve an alert.
        
        Args:
            alert_id: ID of the alert to resolve
            
        Returns:
            True if alert was resolved, False if not found
        """
        alert = self.alerts.get(alert_id)
        if not alert:
            return False
        
        alert.resolved = True
        alert.resolved_at = datetime.now()
        
        logger.info(f"Alert resolved: {alert.title}")
        return True
    
    def register_metric_handler(self, metric_name: str, handler: Callable) -> None:
        """
        Register a handler for a specific metric.
        
        Args:
            metric_name: Name of the metric
            handler: Handler function
        """
        self.metric_handlers[metric_name] = handler
        logger.debug(f"Registered metric handler for: {metric_name}")
    
    def register_alert_handler(self, level: AlertLevel, handler: Callable) -> None:
        """
        Register a handler for alerts of a specific level.
        
        Args:
            level: Alert level
            handler: Handler function
        """
        self.alert_handlers[level].append(handler)
        logger.debug(f"Registered alert handler for level: {level.value}")
    
    def get_metrics_summary(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """
        Get a summary of metrics within a time window.
        
        Args:
            time_window_minutes: Time window in minutes
            
        Returns:
            Metrics summary dictionary
        """
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        
        summary = {
            "time_window_minutes": time_window_minutes,
            "metrics": {},
            "agent_health": {},
            "workflow_stats": {},
            "alerts": {
                "total": len(self.alerts),
                "unresolved": len([a for a in self.alerts.values() if not a.resolved]),
                "by_level": defaultdict(int)
            }
        }
        
        # Aggregate metrics
        for metric_name, points in self.metrics.items():
            recent_points = [p for p in points if p.timestamp > cutoff_time]
            if recent_points:
                values = [p.value for p in recent_points]
                summary["metrics"][metric_name] = {
                    "count": len(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "latest": values[-1]
                }
        
        # Agent health summary
        for agent_name, health_history in self.agent_health_history.items():
            recent_health = [h for h in health_history if h["timestamp"] > cutoff_time]
            if recent_health:
                latest_health = recent_health[-1]
                summary["agent_health"][agent_name] = {
                    "status": latest_health["status"],
                    "success_rate": latest_health["success_rate"],
                    "is_healthy": latest_health["is_healthy"],
                    "data_points": len(recent_health)
                }
        
        # Workflow statistics
        recent_workflows = [
            w for w in self.workflow_metrics.values()
            if w.get("start_time") and w["start_time"] > cutoff_time
        ]
        
        if recent_workflows:
            completed_workflows = [w for w in recent_workflows if w.get("end_time")]
            summary["workflow_stats"] = {
                "total_started": len(recent_workflows),
                "completed": len(completed_workflows),
                "avg_duration": sum(w.get("duration", 0) for w in completed_workflows) / len(completed_workflows) if completed_workflows else 0,
                "success_rate": len([w for w in completed_workflows if w.get("status") == "completed"]) / len(completed_workflows) * 100 if completed_workflows else 0
            }
        
        # Alert summary
        for alert in self.alerts.values():
            summary["alerts"]["by_level"][alert.level.value] += 1
        
        return summary
    
    def _get_agent_distribution(self, tasks: List[PipelineTask]) -> Dict[str, int]:
        """Get distribution of tasks by agent type."""
        distribution = defaultdict(int)
        for task in tasks:
            distribution[task.agent_type.value] += 1
        return dict(distribution)
    
    async def _system_monitor(self) -> None:
        """Background task to monitor system resources."""
        while self._running:
            try:
                if PSUTIL_AVAILABLE:
                    # Collect system metrics
                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    disk = psutil.disk_usage('/')
                    
                    system_data = {
                        "timestamp": datetime.now(),
                        "cpu_percent": cpu_percent,
                        "memory_percent": memory.percent,
                        "memory_available_gb": memory.available / (1024**3),
                        "disk_percent": disk.percent,
                        "disk_free_gb": disk.free / (1024**3)
                    }
                    
                    self.system_metrics.append(system_data)
                    
                    # Record as metrics
                    self.record_metric("system_cpu_percent", cpu_percent)
                    self.record_metric("system_memory_percent", memory.percent)
                    self.record_metric("system_disk_percent", disk.percent)
                    
                    # Check for system alerts
                    if cpu_percent > 90:
                        self.create_alert(
                            level=AlertLevel.WARNING,
                            title="High CPU Usage",
                            message=f"CPU usage is {cpu_percent:.1f}%",
                            metadata={"cpu_percent": cpu_percent}
                        )
                    
                    if memory.percent > 90:
                        self.create_alert(
                            level=AlertLevel.WARNING,
                            title="High Memory Usage",
                            message=f"Memory usage is {memory.percent:.1f}%",
                            metadata={"memory_percent": memory.percent}
                        )
                else:
                    # Mock system metrics if psutil not available
                    system_data = {
                        "timestamp": datetime.now(),
                        "cpu_percent": 25.0,
                        "memory_percent": 45.0,
                        "disk_percent": 60.0
                    }
                    self.system_metrics.append(system_data)
                
                await asyncio.sleep(30)  # Monitor every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in system monitor: {e}")
                await asyncio.sleep(30)
    
    async def _alert_processor(self) -> None:
        """Background task to process and manage alerts."""
        while self._running:
            try:
                # Auto-resolve old alerts
                cutoff_time = datetime.now() - timedelta(hours=24)
                
                for alert in list(self.alerts.values()):
                    if not alert.resolved and alert.timestamp < cutoff_time:
                        if alert.level in [AlertLevel.INFO, AlertLevel.WARNING]:
                            self.resolve_alert(alert.id)
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in alert processor: {e}")
                await asyncio.sleep(300)
    
    async def _metrics_aggregator(self) -> None:
        """Background task to aggregate and clean up metrics."""
        while self._running:
            try:
                # Clean up old metrics (keep last 24 hours)
                cutoff_time = datetime.now() - timedelta(hours=24)
                
                for metric_name, points in self.metrics.items():
                    # Remove old points
                    while points and points[0].timestamp < cutoff_time:
                        points.popleft()
                
                await asyncio.sleep(3600)  # Clean up every hour
                
            except Exception as e:
                logger.error(f"Error in metrics aggregator: {e}")
                await asyncio.sleep(3600)
    
    async def _health_checker(self) -> None:
        """Background task to check overall system health."""
        while self._running:
            try:
                # Check agent health
                unhealthy_agents = []
                for agent_name, health_history in self.agent_health_history.items():
                    if health_history:
                        latest_health = health_history[-1]
                        if not latest_health["is_healthy"]:
                            unhealthy_agents.append(agent_name)
                
                if unhealthy_agents:
                    self.create_alert(
                        level=AlertLevel.ERROR,
                        title="Unhealthy Agents Detected",
                        message=f"Agents reporting unhealthy status: {', '.join(unhealthy_agents)}",
                        metadata={"unhealthy_agents": unhealthy_agents}
                    )
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in health checker: {e}")
                await asyncio.sleep(60)