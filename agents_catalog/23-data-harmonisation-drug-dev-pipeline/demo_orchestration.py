#!/usr/bin/env python3
"""
Demo script for the multi-agent orchestration system.

This script demonstrates how to use the integrated orchestration system
to coordinate the Web Scraper, Data Harmonizer, and Quality Assurance agents.
"""

import asyncio
import logging
from typing import List

from src.orchestration import IntegratedOrchestrationSystem

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Main demo function."""
    
    # Configuration for the orchestration system
    config = {
        "communication": {
            "max_concurrent_messages": 100,
            "message_timeout": 30
        },
        "workflow": {
            "strategy": "dependency",
            "mode": "normal",
            "max_concurrent_tasks": 3,
            "task_timeout": 300,
            "retry_attempts": 2,
            "retry_delay": 5
        },
        "error_handling": {
            "max_error_history": 1000,
            "circuit_breaker_threshold": 5,
            "circuit_breaker_timeout": 60
        },
        "monitoring": {
            "metrics_retention_hours": 24,
            "alert_retention_hours": 48,
            "system_monitoring_interval": 30
        },
        "orchestrator": {
            "web_scraper_concurrency": 2,
            "harmonizer_concurrency": 1,
            "qa_concurrency": 1
        }
    }
    
    # Pharmaceutical company URLs to process
    sources = [
        "https://www.merck.com/research/product-pipeline/",
        "https://www.novonordisk.com/science-and-technology/r-d-pipeline.html",
        "https://www.novartis.com/research-development/novartis-pipeline"
    ]
    
    # Initialize the orchestration system
    logger.info("Initializing integrated orchestration system...")
    orchestration_system = IntegratedOrchestrationSystem(config)
    
    try:
        # Start the system
        logger.info("Starting orchestration system...")
        await orchestration_system.start()
        
        # Get initial system status
        logger.info("Getting system status...")
        status = await orchestration_system.get_system_status()
        logger.info(f"System status: {status['components']}")
        
        # Execute the pipeline
        logger.info(f"Executing pipeline for {len(sources)} sources...")
        result = await orchestration_system.execute_pipeline(sources)
        
        # Display results
        logger.info("Pipeline execution completed!")
        logger.info(f"Execution summary: {result.get('execution_summary', {})}")
        
        # Get final system status
        final_status = await orchestration_system.get_system_status()
        logger.info(f"Final metrics: {final_status.get('metrics', {})}")
        logger.info(f"Alerts: {final_status.get('alerts', {})}")
        logger.info(f"Errors: {final_status.get('errors', {})}")
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        
        # Get error status
        error_status = await orchestration_system.get_system_status()
        logger.error(f"Error details: {error_status.get('errors', {})}")
        
    finally:
        # Stop the system
        logger.info("Stopping orchestration system...")
        await orchestration_system.stop()
        logger.info("Demo completed")


def demo_configuration():
    """Demonstrate different configuration options."""
    
    print("=== Orchestration System Configuration Options ===\n")
    
    print("1. Workflow Strategies:")
    print("   - SEQUENTIAL: Execute tasks one by one")
    print("   - PARALLEL: Execute independent tasks in parallel")
    print("   - PRIORITY: Execute by priority order")
    print("   - DEPENDENCY: Execute based on dependency resolution (recommended)")
    
    print("\n2. Execution Modes:")
    print("   - NORMAL: Normal execution")
    print("   - FAST_FAIL: Stop on first failure")
    print("   - CONTINUE: Continue despite failures")
    print("   - RETRY: Retry failed tasks")
    
    print("\n3. Error Recovery Strategies:")
    print("   - RETRY: Retry with exponential backoff")
    print("   - FALLBACK: Use alternative method")
    print("   - SKIP: Skip failed task")
    print("   - ABORT: Abort the operation")
    print("   - ESCALATE: Escalate to human intervention")
    print("   - RESTART: Restart the agent")
    
    print("\n4. Monitoring Features:")
    print("   - Real-time metrics collection")
    print("   - Agent health monitoring")
    print("   - System resource monitoring")
    print("   - Automated alerting")
    print("   - OpenTelemetry integration")
    print("   - Langfuse LLM observability")
    
    print("\n5. Communication Protocols:")
    print("   - REQUEST_RESPONSE: Request-response pattern")
    print("   - PUBLISH_SUBSCRIBE: Pub-sub messaging")
    print("   - BROADCAST: Broadcast to all agents")
    print("   - DIRECT_MESSAGE: Direct agent-to-agent messaging")


async def demo_error_handling():
    """Demonstrate error handling capabilities."""
    
    print("\n=== Error Handling Demo ===\n")
    
    # Simulate different types of errors
    from src.orchestration.error_handler import ErrorHandler, ErrorCategory
    
    error_handler = ErrorHandler()
    
    # Network error
    network_error = ConnectionError("Failed to connect to server")
    await error_handler.handle_error(
        error=network_error,
        task_id="test_task_1",
        agent_name="web_scraper"
    )
    
    # Timeout error
    timeout_error = TimeoutError("Request timed out")
    await error_handler.handle_error(
        error=timeout_error,
        task_id="test_task_2",
        agent_name="data_harmonizer"
    )
    
    # Validation error
    validation_error = ValueError("Invalid data format")
    await error_handler.handle_error(
        error=validation_error,
        task_id="test_task_3",
        agent_name="quality_assurance"
    )
    
    # Get error statistics
    stats = error_handler.get_error_statistics()
    print(f"Error statistics: {stats}")


async def demo_monitoring():
    """Demonstrate monitoring capabilities."""
    
    print("\n=== Monitoring Demo ===\n")
    
    from src.orchestration.monitoring import CentralizedMonitor, MetricType, AlertLevel
    
    monitor = CentralizedMonitor()
    await monitor.start()
    
    try:
        # Record some metrics
        monitor.record_metric("test_counter", 1, metric_type=MetricType.COUNTER)
        monitor.record_metric("test_gauge", 75.5, labels={"component": "demo"})
        monitor.record_metric("test_histogram", 0.123, metric_type=MetricType.HISTOGRAM)
        
        # Create alerts
        monitor.create_alert(
            level=AlertLevel.INFO,
            title="Demo Alert",
            message="This is a demo alert",
            source="demo"
        )
        
        monitor.create_alert(
            level=AlertLevel.WARNING,
            title="Demo Warning",
            message="This is a demo warning",
            source="demo"
        )
        
        # Get metrics summary
        summary = monitor.get_metrics_summary(time_window_minutes=5)
        print(f"Metrics summary: {summary}")
        
    finally:
        await monitor.stop()


if __name__ == "__main__":
    print("=== Multi-Agent Orchestration System Demo ===\n")
    
    # Show configuration options
    demo_configuration()
    
    # Run error handling demo
    asyncio.run(demo_error_handling())
    
    # Run monitoring demo
    asyncio.run(demo_monitoring())
    
    # Run main orchestration demo
    print("\n=== Running Main Orchestration Demo ===\n")
    asyncio.run(main())