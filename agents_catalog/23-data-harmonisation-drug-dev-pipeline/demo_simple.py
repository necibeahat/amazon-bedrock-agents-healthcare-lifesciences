#!/usr/bin/env python3
"""
Simple demo script showing the pharmaceutical pipeline data collection and harmonization.
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


async def demo_pharmaceutical_pipeline():
    """Demonstrate the pharmaceutical pipeline data collection and harmonization."""
    
    # Configuration for Graph-based execution
    config = {
        "orchestrator": {
            "execution_mode": "graph",  # Use Graph pattern for structured workflow
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
    
    # Initialize the system
    system = IntegratedOrchestrationSystem(config)
    
    try:
        # Start the system
        logger.info("🚀 Starting Pharmaceutical Pipeline System...")
        await system.start()
        
        # Get system status
        status = await system.get_system_status()
        logger.info(f"✅ System ready: {status['framework']} with {len(status['strands_agents'])} agents")
        
        # Pharmaceutical company pipeline URLs
        pharma_sources = [
            "https://www.merck.com/research/product-pipeline/",
            "https://www.novonordisk.com/science-and-technology/r-d-pipeline.html",
            "https://www.novartis.com/research-development/novartis-pipeline"
        ]
        
        logger.info(f"📊 Processing {len(pharma_sources)} pharmaceutical pipeline sources...")
        logger.info("🔄 Executing: Web Scraping → Data Harmonization → Quality Assurance")
        
        # Execute the pipeline
        start_time = asyncio.get_event_loop().time()
        result = await system.execute_pipeline_with_graph(pharma_sources)
        end_time = asyncio.get_event_loop().time()
        
        # Extract results
        graph_result = result.get('graph_result')
        if graph_result:
            logger.info("=" * 60)
            logger.info("📈 PIPELINE EXECUTION RESULTS")
            logger.info("=" * 60)
            logger.info(f"Status: {graph_result.status}")
            logger.info(f"Total execution time: {end_time - start_time:.2f} seconds")
            logger.info(f"Nodes executed: {len(graph_result.execution_order)}")
            
            # Show execution order
            logger.info("\n🔄 Execution Order:")
            for i, node in enumerate(graph_result.execution_order, 1):
                logger.info(f"  {i}. {node.node_id} ({node.execution_status})")
            
            # Show results from each agent
            logger.info("\n📋 Agent Results:")
            for node_id, node_result in graph_result.results.items():
                logger.info(f"\n🤖 {node_id.upper()} AGENT:")
                logger.info(f"  Status: {node_result.status}")
                logger.info(f"  Execution time: {node_result.execution_time}ms")
                
                # Extract and display key information from the result
                if hasattr(node_result, 'result') and node_result.result:
                    result_content = str(node_result.result)
                    # Show first 200 characters of the result
                    preview = result_content[:200] + "..." if len(result_content) > 200 else result_content
                    logger.info(f"  Result preview: {preview}")
            
            # Show final system metrics
            final_status = await system.get_system_status()
            if final_status.get('communication_metrics'):
                logger.info("\n📊 Communication Metrics:")
                comm_metrics = final_status['communication_metrics']
                total_messages = sum(comm_metrics.get('messages_sent', {}).values())
                total_processed = sum(comm_metrics.get('messages_processed', {}).values())
                total_errors = sum(comm_metrics.get('error_counts', {}).values())
                
                logger.info(f"  Messages sent: {total_messages}")
                logger.info(f"  Messages processed: {total_processed}")
                logger.info(f"  Errors: {total_errors}")
            
            logger.info("=" * 60)
            logger.info("✅ Pharmaceutical pipeline execution completed successfully!")
            logger.info("📊 Data has been collected, harmonized, and quality-assured")
            logger.info("=" * 60)
        
        else:
            logger.warning("⚠️  No detailed results available")
        
    except Exception as e:
        logger.error(f"❌ Pipeline execution failed: {e}")
        raise
    
    finally:
        # Stop the system
        logger.info("🛑 Stopping pharmaceutical pipeline system...")
        await system.stop()
        logger.info("👋 System shutdown complete")


def main():
    """Main demo function."""
    logger.info("🧬 Pharmaceutical Pipeline Data Harmonization Demo")
    logger.info("=" * 60)
    
    try:
        asyncio.run(demo_pharmaceutical_pipeline())
        
    except KeyboardInterrupt:
        logger.info("⏹️  Demo interrupted by user")
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        raise


if __name__ == "__main__":
    main()