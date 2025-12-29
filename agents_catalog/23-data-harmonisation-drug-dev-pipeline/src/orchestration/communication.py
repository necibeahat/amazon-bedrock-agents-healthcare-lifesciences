"""
Communication protocols and messaging system for multi-agent coordination.

This module implements the communication layer using Strands framework
for reliable message passing between agents in the pipeline.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Callable, Any, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict

from strands import Agent
from strands.multiagent import Swarm, GraphBuilder
from strands.types.content import ContentBlock, Message as StrandsMessage

from ..models.pipeline import AgentMessage, TaskRequest, TaskResponse, AgentHealth
from ..utils.logging import get_logger

logger = get_logger(__name__)


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class CommunicationProtocol(Enum):
    """Communication protocol types."""
    REQUEST_RESPONSE = "request_response"
    PUBLISH_SUBSCRIBE = "publish_subscribe"
    BROADCAST = "broadcast"
    DIRECT_MESSAGE = "direct_message"


@dataclass
class MessageHandler:
    """
    Message handler configuration for Strands agents.
    
    Attributes:
        message_type: Type of message to handle
        handler_func: Function to handle the message
        priority: Handler priority
        timeout: Handler timeout in seconds
    """
    message_type: str
    handler_func: Callable[[AgentMessage], Any]
    priority: int = 1
    timeout: Optional[int] = None


@dataclass
class PendingRequest:
    """
    Tracking for pending request-response messages.
    
    Attributes:
        request_id: Unique request identifier
        sender: Agent that sent the request
        recipient: Agent that should respond
        timestamp: When request was sent
        timeout: Request timeout
        future: Future for the response
    """
    request_id: str
    sender: str
    recipient: str
    timestamp: datetime
    timeout: int
    future: asyncio.Future


@dataclass
class CommunicationMetrics:
    """Metrics for communication monitoring."""
    messages_sent: Dict[str, int]
    messages_processed: Dict[str, int]
    response_times: Dict[str, List[float]]
    error_counts: Dict[str, int]
    
    def __init__(self):
        self.messages_sent = defaultdict(int)
        self.messages_processed = defaultdict(int)
        self.response_times = defaultdict(list)
        self.error_counts = defaultdict(int)
    
    def record_message_sent(self, sender: str, recipient: str, message_type: str):
        """Record a sent message."""
        key = f"{sender}->{recipient}:{message_type}"
        self.messages_sent[key] += 1
    
    def record_message_processed(self, recipient: str, message_type: str):
        """Record a processed message."""
        key = f"{recipient}:{message_type}"
        self.messages_processed[key] += 1
    
    def record_response_time(self, request_type: str, response_time: float):
        """Record response time for a request."""
        self.response_times[request_type].append(response_time)
    
    def record_error(self, error_type: str):
        """Record an error."""
        self.error_counts[error_type] += 1


class AgentCommunicationManager:
    """
    Manages communication between agents in the multi-agent system using Strands framework.
    
    Provides reliable message passing, request-response patterns,
    publish-subscribe messaging, and agent health monitoring through Strands orchestration.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the communication manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.metrics_collector = CommunicationMetrics()
        
        # Agent tracking
        self.registered_agents: Dict[str, Agent] = {}
        self.agent_health: Dict[str, AgentHealth] = {}
        
        # Message handling
        self.handlers: Dict[str, List[MessageHandler]] = defaultdict(list)
        self.pending_requests: Dict[str, PendingRequest] = {}
        self.subscriptions: Dict[str, Set[str]] = defaultdict(set)
        
        # Message queues by priority
        self.message_queues: Dict[MessagePriority, asyncio.Queue] = {
            priority: asyncio.Queue() for priority in MessagePriority
        }
        
        # Background tasks
        self._background_tasks: List[asyncio.Task] = []
        self._running = False
        
        # Strands orchestration components
        self.swarm: Optional[Swarm] = None
        self.graph = None
        
        logger.info("Strands agent communication manager initialized")
    
    async def start(self) -> None:
        """Start the communication manager."""
        if self._running:
            return
        
        self._running = True
        
        # Start background tasks
        self._background_tasks = [
            asyncio.create_task(self._message_processor()),
            asyncio.create_task(self._health_monitor()),
            asyncio.create_task(self._cleanup_expired_requests())
        ]
        
        logger.info("Strands communication manager started")
    
    async def stop(self) -> None:
        """Stop the communication manager."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        logger.info("Strands communication manager stopped")
    
    def register_agent(self, agent_name: str, agent: Agent) -> None:
        """
        Register a Strands agent with the communication manager.
        
        Args:
            agent_name: Name of the agent to register
            agent: Strands Agent instance
        """
        self.registered_agents[agent_name] = agent
        self.agent_health[agent_name] = AgentHealth(
            agent_name=agent_name,
            status="healthy",
            last_heartbeat=datetime.now()
        )
        
        logger.info(f"Strands agent {agent_name} registered")
    
    def unregister_agent(self, agent_name: str) -> None:
        """
        Unregister an agent from the communication manager.
        
        Args:
            agent_name: Name of the agent to unregister
        """
        self.registered_agents.pop(agent_name, None)
        self.agent_health.pop(agent_name, None)
        
        # Remove subscriptions
        for topic in list(self.subscriptions.keys()):
            self.subscriptions[topic].discard(agent_name)
            if not self.subscriptions[topic]:
                del self.subscriptions[topic]
        
        logger.info(f"Agent {agent_name} unregistered")
    
    async def setup_swarm_communication(self, agents: List[Agent]) -> None:
        """
        Set up Swarm-based communication between agents.
        
        Args:
            agents: List of Strands agents to include in the swarm
        """
        try:
            self.swarm = Swarm(
                agents=agents,
                max_handoffs=20,
                max_iterations=20,
                execution_timeout=900.0,
                node_timeout=300.0,
                repetitive_handoff_detection_window=8,
                repetitive_handoff_min_unique_agents=3
            )
            
            logger.info(f"Swarm communication setup with {len(agents)} agents")
            
        except Exception as e:
            logger.error(f"Failed to setup swarm communication: {e}")
            raise
    
    async def setup_graph_communication(self, agents: Dict[str, Agent], dependencies: List[tuple]) -> None:
        """
        Set up Graph-based communication between agents.
        
        Args:
            agents: Dictionary mapping agent names to Agent instances
            dependencies: List of (from_agent, to_agent) dependency tuples
        """
        try:
            builder = GraphBuilder()
            
            # Add agents as nodes
            for agent_name, agent in agents.items():
                builder.add_node(agent, agent_name)
            
            # Add dependencies as edges
            for from_agent, to_agent in dependencies:
                builder.add_edge(from_agent, to_agent)
            
            # Set entry point (first agent in the list)
            if agents:
                first_agent = next(iter(agents.keys()))
                builder.set_entry_point(first_agent)
            
            # Configure execution limits
            builder.set_execution_timeout(600)
            builder.set_node_timeout(300)
            
            # Build the graph
            self.graph = builder.build()
            
            logger.info(f"Graph communication setup with {len(agents)} agents and {len(dependencies)} dependencies")
            
        except Exception as e:
            logger.error(f"Failed to setup graph communication: {e}")
            raise
    
    def register_handler(
        self,
        agent_name: str,
        message_type: str,
        handler_func: Callable[[AgentMessage], Any],
        priority: int = 1,
        timeout: Optional[int] = None
    ) -> None:
        """
        Register a message handler for an agent.
        
        Args:
            agent_name: Name of the agent
            message_type: Type of message to handle
            handler_func: Function to handle the message
            priority: Handler priority
            timeout: Handler timeout in seconds
        """
        handler = MessageHandler(
            message_type=message_type,
            handler_func=handler_func,
            priority=priority,
            timeout=timeout
        )
        
        handler_key = f"{agent_name}:{message_type}"
        self.handlers[handler_key].append(handler)
        
        logger.debug(f"Registered handler for {agent_name}:{message_type}")
    
    async def send_message_via_swarm(
        self,
        task_description: str,
        invocation_state: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Send a message through the Swarm orchestration pattern.
        
        Args:
            task_description: Description of the task for the swarm
            invocation_state: Optional state to pass to all agents
            
        Returns:
            Swarm execution result
        """
        if not self.swarm:
            raise ValueError("Swarm communication not set up. Call setup_swarm_communication first.")
        
        try:
            start_time = datetime.now()
            
            # Execute the swarm
            result = await self.swarm.invoke_async(task_description, invocation_state=invocation_state)
            
            # Record metrics
            execution_time = (datetime.now() - start_time).total_seconds()
            self.metrics_collector.record_response_time("swarm_execution", execution_time)
            
            logger.info(f"Swarm message execution completed in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            self.metrics_collector.record_error("swarm_execution_error")
            logger.error(f"Swarm message execution failed: {e}")
            raise
    
    async def send_message_via_graph(
        self,
        task_description: str,
        invocation_state: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Send a message through the Graph orchestration pattern.
        
        Args:
            task_description: Description of the task for the graph
            invocation_state: Optional state to pass to all agents
            
        Returns:
            Graph execution result
        """
        if not self.graph:
            raise ValueError("Graph communication not set up. Call setup_graph_communication first.")
        
        try:
            start_time = datetime.now()
            
            # Execute the graph
            result = await self.graph.invoke_async(task_description, invocation_state=invocation_state)
            
            # Record metrics
            execution_time = (datetime.now() - start_time).total_seconds()
            self.metrics_collector.record_response_time("graph_execution", execution_time)
            
            logger.info(f"Graph message execution completed in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            self.metrics_collector.record_error("graph_execution_error")
            logger.error(f"Graph message execution failed: {e}")
            raise
    
    async def send_message(
        self,
        sender: str,
        recipient: str,
        message_type: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Send a message to another agent using Strands communication.
        
        Args:
            sender: Sending agent name
            recipient: Receiving agent name
            message_type: Type of message
            payload: Message payload
            priority: Message priority
            correlation_id: Correlation ID for tracking
        """
        message = AgentMessage(
            id=f"{sender}_{recipient}_{datetime.now().timestamp()}",
            sender=sender,
            recipient=recipient,
            message_type=message_type,
            payload=payload,
            correlation_id=correlation_id
        )
        
        # Add to appropriate priority queue
        await self.message_queues[priority].put(message)
        
        # Record metrics
        self.metrics_collector.record_message_sent(sender, recipient, message_type)
        
        logger.debug(f"Message queued: {sender} -> {recipient} ({message_type})")
    
    async def send_request(
        self,
        sender: str,
        recipient: str,
        request_type: str,
        payload: Dict[str, Any],
        timeout: int = 30
    ) -> Any:
        """
        Send a request and wait for response using Strands agents.
        
        Args:
            sender: Sending agent name
            recipient: Receiving agent name
            request_type: Type of request
            payload: Request payload
            timeout: Request timeout in seconds
            
        Returns:
            Response payload
        """
        request_id = f"req_{sender}_{recipient}_{datetime.now().timestamp()}"
        
        # Create future for response
        response_future = asyncio.Future()
        
        # Track pending request
        self.pending_requests[request_id] = PendingRequest(
            request_id=request_id,
            sender=sender,
            recipient=recipient,
            timestamp=datetime.now(),
            timeout=timeout,
            future=response_future
        )
        
        # Send request message
        await self.send_message(
            sender=sender,
            recipient=recipient,
            message_type=f"request:{request_type}",
            payload={**payload, "request_id": request_id},
            priority=MessagePriority.HIGH,
            correlation_id=request_id
        )
        
        try:
            # Wait for response
            start_time = datetime.now()
            response = await asyncio.wait_for(response_future, timeout=timeout)
            
            # Record response time
            response_time = (datetime.now() - start_time).total_seconds()
            self.metrics_collector.record_response_time(request_type, response_time)
            
            return response
        except asyncio.TimeoutError:
            self.metrics_collector.record_error("request_timeout")
            logger.error(f"Request {request_id} timed out")
            raise
        finally:
            # Clean up pending request
            self.pending_requests.pop(request_id, None)
    
    async def send_response(
        self,
        sender: str,
        recipient: str,
        request_id: str,
        payload: Dict[str, Any]
    ) -> None:
        """
        Send a response to a request.
        
        Args:
            sender: Sending agent name
            recipient: Receiving agent name (original requester)
            request_id: ID of the original request
            payload: Response payload
        """
        await self.send_message(
            sender=sender,
            recipient=recipient,
            message_type="response",
            payload={**payload, "request_id": request_id},
            priority=MessagePriority.HIGH,
            correlation_id=request_id
        )
    
    def subscribe(self, agent_name: str, topic: str) -> None:
        """
        Subscribe an agent to a topic.
        
        Args:
            agent_name: Name of the agent
            topic: Topic to subscribe to
        """
        self.subscriptions[topic].add(agent_name)
        logger.debug(f"Agent {agent_name} subscribed to topic {topic}")
    
    def unsubscribe(self, agent_name: str, topic: str) -> None:
        """
        Unsubscribe an agent from a topic.
        
        Args:
            agent_name: Name of the agent
            topic: Topic to unsubscribe from
        """
        self.subscriptions[topic].discard(agent_name)
        if not self.subscriptions[topic]:
            del self.subscriptions[topic]
        logger.debug(f"Agent {agent_name} unsubscribed from topic {topic}")
    
    async def publish(
        self,
        sender: str,
        topic: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> None:
        """
        Publish a message to a topic.
        
        Args:
            sender: Publishing agent name
            topic: Topic to publish to
            payload: Message payload
            priority: Message priority
        """
        subscribers = self.subscriptions.get(topic, set())
        
        for subscriber in subscribers:
            await self.send_message(
                sender=sender,
                recipient=subscriber,
                message_type=f"topic:{topic}",
                payload=payload,
                priority=priority
            )
        
        logger.debug(f"Published to topic {topic} for {len(subscribers)} subscribers")
    
    async def broadcast(
        self,
        sender: str,
        message_type: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> None:
        """
        Broadcast a message to all registered agents.
        
        Args:
            sender: Broadcasting agent name
            message_type: Type of message
            payload: Message payload
            priority: Message priority
        """
        for agent_name in self.registered_agents.keys():
            if agent_name != sender:  # Don't send to self
                await self.send_message(
                    sender=sender,
                    recipient=agent_name,
                    message_type=message_type,
                    payload=payload,
                    priority=priority
                )
        
        logger.debug(f"Broadcast {message_type} to {len(self.registered_agents) - 1} agents")
    
    async def update_agent_health(self, agent_name: str, health_data: Dict[str, Any]) -> None:
        """
        Update agent health information.
        
        Args:
            agent_name: Name of the agent
            health_data: Health data dictionary
        """
        if agent_name in self.agent_health:
            health = self.agent_health[agent_name]
            health.last_heartbeat = datetime.now()
            health.status = health_data.get("status", health.status)
            health.active_tasks = health_data.get("active_tasks", health.active_tasks)
            health.memory_usage = health_data.get("memory_usage", health.memory_usage)
            health.cpu_usage = health_data.get("cpu_usage", health.cpu_usage)
            
            logger.debug(f"Updated health for agent {agent_name}")
    
    def get_agent_health(self, agent_name: str) -> Optional[AgentHealth]:
        """
        Get health information for an agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Agent health information or None if not found
        """
        return self.agent_health.get(agent_name)
    
    def get_all_agent_health(self) -> Dict[str, AgentHealth]:
        """
        Get health information for all agents.
        
        Returns:
            Dictionary mapping agent names to health information
        """
        return self.agent_health.copy()
    
    def get_communication_metrics(self) -> Dict[str, Any]:
        """
        Get communication metrics.
        
        Returns:
            Dictionary containing communication metrics
        """
        return {
            "messages_sent": dict(self.metrics_collector.messages_sent),
            "messages_processed": dict(self.metrics_collector.messages_processed),
            "response_times": {
                k: {
                    "count": len(v),
                    "avg": sum(v) / len(v) if v else 0,
                    "min": min(v) if v else 0,
                    "max": max(v) if v else 0
                }
                for k, v in self.metrics_collector.response_times.items()
            },
            "error_counts": dict(self.metrics_collector.error_counts)
        }
    
    async def _message_processor(self) -> None:
        """Background task to process messages by priority."""
        while self._running:
            try:
                # Process messages in priority order
                for priority in sorted(MessagePriority, key=lambda p: p.value, reverse=True):
                    queue = self.message_queues[priority]
                    
                    try:
                        # Try to get a message without blocking
                        message = queue.get_nowait()
                        await self._handle_message(message)
                        queue.task_done()
                    except asyncio.QueueEmpty:
                        continue
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.01)
                
            except Exception as e:
                self.metrics_collector.record_error("message_processor_error")
                logger.error(f"Error in message processor: {e}")
                await asyncio.sleep(1)
    
    async def _handle_message(self, message: AgentMessage) -> None:
        """
        Handle a single message using Strands agents.
        
        Args:
            message: Message to handle
        """
        try:
            # Check if this is a response to a pending request
            if message.message_type == "response":
                request_id = message.payload.get("request_id")
                if request_id in self.pending_requests:
                    pending = self.pending_requests[request_id]
                    if not pending.future.done():
                        pending.future.set_result(message.payload)
                    return
            
            # Find handlers for this message
            handler_key = f"{message.recipient}:{message.message_type}"
            handlers = self.handlers.get(handler_key, [])
            
            if not handlers:
                logger.warning(f"No handler found for {handler_key}")
                return
            
            # Execute handlers in priority order
            for handler in sorted(handlers, key=lambda h: h.priority, reverse=True):
                try:
                    if handler.timeout:
                        await asyncio.wait_for(
                            handler.handler_func(message),
                            timeout=handler.timeout
                        )
                    else:
                        await handler.handler_func(message)
                except Exception as e:
                    self.metrics_collector.record_error("handler_error")
                    logger.error(f"Handler error for {handler_key}: {e}")
            
            # Record metrics
            self.metrics_collector.record_message_processed(
                message.recipient, message.message_type
            )
            
        except Exception as e:
            self.metrics_collector.record_error("message_handling_error")
            logger.error(f"Error handling message {message.id}: {e}")
    
    async def _health_monitor(self) -> None:
        """Background task to monitor agent health."""
        while self._running:
            try:
                now = datetime.now()
                unhealthy_agents = []
                
                for agent_name, health in self.agent_health.items():
                    # Check if agent hasn't sent heartbeat recently
                    heartbeat_age = (now - health.last_heartbeat).total_seconds()
                    
                    if heartbeat_age > 60:  # 60 seconds threshold
                        health.status = "unhealthy"
                        unhealthy_agents.append(agent_name)
                
                if unhealthy_agents:
                    logger.warning(f"Unhealthy agents detected: {unhealthy_agents}")
                
                # Sleep for 30 seconds before next check
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in health monitor: {e}")
                await asyncio.sleep(30)
    
    async def _cleanup_expired_requests(self) -> None:
        """Background task to clean up expired requests."""
        while self._running:
            try:
                now = datetime.now()
                expired_requests = []
                
                for request_id, pending in self.pending_requests.items():
                    age = (now - pending.timestamp).total_seconds()
                    if age > pending.timeout:
                        expired_requests.append(request_id)
                
                # Clean up expired requests
                for request_id in expired_requests:
                    pending = self.pending_requests.pop(request_id, None)
                    if pending and not pending.future.done():
                        pending.future.set_exception(
                            TimeoutError(f"Request {request_id} expired")
                        )
                
                if expired_requests:
                    self.metrics_collector.record_error("expired_requests")
                    logger.warning(f"Cleaned up {len(expired_requests)} expired requests")
                
                # Sleep for 60 seconds before next cleanup
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in request cleanup: {e}")
                await asyncio.sleep(60)