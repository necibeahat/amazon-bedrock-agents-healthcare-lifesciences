#!/usr/bin/env python3
"""
Demo script for Strands-based multi-agent orchestration.

This script demonstrates how to use the updated orchestration system
with actual Strands Agent SDK for pharmaceutical pipeline data processing.
"""

import asyncio
import logging
from typing import List

from src.orchestration.integration import IntegratedOrchestrationSystem

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def demo_strands_orchestration():
    """Demonstrate Strands-based multi-agent orchestration."""
    
    # Configuration for the integrated system
    config = {
        "orchestrator": {
            "execution_mode": "graph",  # Can be "graph" or "swarm"
            "web_scraper_concurrency": 3,
            "harmonizer_concurrency": 2,
            "qa_concurrency": 1
        },
        "communication": {
            "timeout": 300,
            "retry_attempts": 3
        },
        "workflow": {
            "max_concurrent_tasks": 5,
            "task_timeout": 600
        },
        "error_handling": {
            "max_retries": 3,
            "retry_delay": 5
        },
        "monitoring": {
            "metrics_retention_hours": 24,
            "alert_threshold": 5
        }
    }
    
    # Initialize the integrated orchestration system
    system = IntegratedOrchestrationSystem(config)
    
    try:
        # Start the system
        logger.info("Starting Strands orchestration system...")
        await system.start()
        
        # Get initial system status
        status = await system.get_system_status()
        logger.info(f"System status: {status['framework']} - {len(status['strands_agents'])} agents")
        
        # Demo pharmaceutical company URLs (these would be real URLs in production)
        demo_sources = [
            "https://www.merck.com/research/product-pipeline/",
            "https://www.novonordisk.com/science-and-technology/r-d-pipeline.html",
            "https://www.novartis.com/research-development/novartis-pipeline"
        ]
        
        logger.info(f"Executing pipeline for {len(demo_sources)} sources...")
        
        # Execute pipeline using Graph pattern (default)
        logger.info("=== Executing with Graph Pattern ===")
        graph_result = await system.execute_pipeline_with_graph(demo_sources)
        
        # Extract the actual GraphResult from the wrapper
        actual_graph_result = graph_result.get('graph_result')
        if actual_graph_result:
            logger.info(f"Graph execution completed: {actual_graph_result.status}")
            logger.info(f"Nodes executed: {len(actual_graph_result.execution_order)}")
            logger.info(f"Execution time: {actual_graph_result.execution_time}ms")
        else:
            logger.info("Graph execution completed (no detailed result)")
        
        # Execute pipeline using Swarm pattern
        logger.info("=== Executing with Swarm Pattern ===")
        swarm_result = await system.execute_pipeline_with_swarm(demo_sources)
        
        # Extract the actual SwarmResult from the wrapper
        actual_swarm_result = swarm_result.get('swarm_result')
        if actual_swarm_result:
            logger.info(f"Swarm execution completed: {actual_swarm_result.status}")
            logger.info(f"Iterations: {actual_swarm_result.execution_count}")
        else:
            logger.info("Swarm execution completed (no detailed result)")
        
        # Execute using the main orchestrator (uses configured execution mode)
        logger.info("=== Executing with Main Orchestrator ===")
        main_result = await system.execute_pipeline(demo_sources)
        execution_summary = main_result.get('execution_summary', {})
        logger.info(f"Main orchestrator execution completed: {execution_summary.get('status', 'unknown')}")
        
        # Get final system status
        final_status = await system.get_system_status()
        logger.info("=== Final System Status ===")
        logger.info(f"Framework: {final_status['framework']}")
        logger.info(f"Orchestration patterns: {final_status['orchestration_patterns']}")
        logger.info(f"Strands agents: {list(final_status['strands_agents'].keys())}")
        
        # Display metrics
        if final_status.get('communication_metrics'):
            logger.info("=== Communication Metrics ===")
            comm_metrics = final_status['communication_metrics']
            logger.info(f"Messages sent: {sum(comm_metrics.get('messages_sent', {}).values())}")
            logger.info(f"Messages processed: {sum(comm_metrics.get('messages_processed', {}).values())}")
            logger.info(f"Error count: {sum(comm_metrics.get('error_counts', {}).values())}")
        
        logger.info("Demo completed successfully!")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise
    
    finally:
        # Stop the system
        logger.info("Stopping Strands orchestration system...")
        await system.stop()


async def demo_individual_patterns():
    """Demonstrate individual Strands orchestration patterns."""
    
    logger.info("=== Individual Pattern Demonstrations ===")
    
    config = {
        "orchestrator": {
            "execution_mode": "graph",
            "web_scraper_concurrency": 2,
            "harmonizer_concurrency": 1,
            "qa_concurrency": 1
        }
    }
    
    system = IntegratedOrchestrationSystem(config)
    
    try:
        await system.start()
        
        demo_sources = ["https://example-pharma.com/pipeline"]
        
        # Test Graph pattern
        logger.info("Testing Graph pattern for structured workflow...")
        graph_result = await system.execute_pipeline_with_graph(demo_sources)
        
        actual_graph_result = graph_result.get('graph_result')
        if actual_graph_result:
            logger.info(f"Graph pattern: {actual_graph_result.status} in {actual_graph_result.execution_time}ms")
        
        # Test Swarm pattern
        logger.info("Testing Swarm pattern for collaborative agents...")
        swarm_result = await system.execute_pipeline_with_swarm(demo_sources)
        
        actual_swarm_result = swarm_result.get('swarm_result')
        if actual_swarm_result:
            logger.info(f"Swarm pattern: {actual_swarm_result.status}")
        
        logger.info("Individual pattern demonstrations completed!")
        
    except Exception as e:
        logger.error(f"Pattern demo failed: {e}")
        raise
    
    finally:
        await system.stop()


def main():
    """Main demo function."""
    logger.info("Starting Strands Agent SDK Orchestration Demo")
    logger.info("=" * 50)
    
    try:
        # Run main orchestration demo
        asyncio.run(demo_strands_orchestration())
        
        logger.info("\n" + "=" * 50)
        
        # Run individual pattern demos
        asyncio.run(demo_individual_patterns())
        
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed with error: {e}")
        raise


if __name__ == "__main__":
    main()