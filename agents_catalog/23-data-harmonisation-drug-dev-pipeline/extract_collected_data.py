#!/usr/bin/env python3
"""
Extract and display the collected and harmonized data from the recent pipeline execution.
"""

import asyncio
import logging
import json
from typing import Dict, Any
from datetime import datetime

from src.orchestration.integration import IntegratedOrchestrationSystem

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def extract_pipeline_data():
    """Extract and display the collected data from the pipeline execution."""
    
    # Configuration for the system
    config = {
        "orchestrator": {
            "execution_mode": "graph",
            "web_scraper_concurrency": 3,
            "harmonizer_concurrency": 2,
            "qa_concurrency": 1
        }
    }
    
    # Initialize the system
    system = IntegratedOrchestrationSystem(config)
    
    try:
        # Start the system
        logger.info("🔍 Starting data extraction system...")
        await system.start()
        
        # Pharmaceutical company pipeline URLs
        pharma_sources = [
            "https://www.merck.com/research/product-pipeline/",
            "https://www.novonordisk.com/science-and-technology/r-d-pipeline.html",
            "https://www.novartis.com/research-development/novartis-pipeline"
        ]
        
        logger.info("📊 Executing pipeline to collect fresh data...")
        
        # Execute the pipeline and capture detailed results
        result = await system.execute_pipeline_with_graph(pharma_sources)
        
        # Extract the GraphResult
        graph_result = result.get('graph_result')
        if not graph_result:
            logger.error("❌ No graph result available")
            return
        
        logger.info("=" * 80)
        logger.info("📈 COLLECTED AND HARMONIZED PHARMACEUTICAL DATA")
        logger.info("=" * 80)
        
        # Display execution summary
        logger.info(f"✅ Pipeline Status: {graph_result.status}")
        logger.info(f"⏱️  Total Execution Time: {graph_result.execution_time}ms")
        logger.info(f"🔄 Nodes Executed: {len(graph_result.execution_order)}")
        
        # Extract and display data from each agent
        collected_data = {}
        
        for node_id, node_result in graph_result.results.items():
            logger.info(f"\n🤖 {node_id.upper()} AGENT RESULTS:")
            logger.info(f"   Status: {node_result.status}")
            logger.info(f"   Execution Time: {node_result.execution_time}ms")
            
            if hasattr(node_result, 'result') and node_result.result:
                # Extract the actual result content
                result_content = str(node_result.result)
                
                # Try to extract structured data if available
                if "collected data" in result_content.lower() or "pipeline data" in result_content.lower():
                    logger.info(f"   📊 Data Collection Summary:")
                    
                    # Look for specific data patterns
                    lines = result_content.split('\n')
                    for line in lines[:20]:  # First 20 lines for summary
                        if any(keyword in line.lower() for keyword in ['merck', 'novartis', 'novo nordisk', 'compounds', 'drugs', 'pipeline']):
                            logger.info(f"      • {line.strip()}")
                
                # Store the full result for analysis
                collected_data[node_id] = {
                    'status': str(node_result.status),
                    'execution_time_ms': node_result.execution_time,
                    'result_preview': result_content[:500] + "..." if len(result_content) > 500 else result_content,
                    'full_result': result_content
                }
        
        # Save the collected data to a file for inspection
        output_file = f"collected_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        output_data = {
            "extraction_timestamp": datetime.now().isoformat(),
            "pipeline_status": str(graph_result.status),
            "total_execution_time_ms": graph_result.execution_time,
            "execution_order": [node.node_id for node in graph_result.execution_order],
            "agent_results": collected_data,
            "sources_processed": pharma_sources
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n💾 Full results saved to: {output_file}")
        
        # Display key insights
        logger.info("\n🔍 KEY INSIGHTS:")
        
        # Check for data collection indicators
        web_scraper_result = collected_data.get('web_scraper', {}).get('full_result', '')
        if 'merck' in web_scraper_result.lower():
            logger.info("   ✅ Merck pipeline data detected")
        if 'novartis' in web_scraper_result.lower():
            logger.info("   ✅ Novartis pipeline data detected")
        if 'novo nordisk' in web_scraper_result.lower():
            logger.info("   ✅ Novo Nordisk pipeline data detected")
        
        # Check for harmonization indicators
        harmonizer_result = collected_data.get('data_harmonizer', {}).get('full_result', '')
        if 'harmonized' in harmonizer_result.lower() or 'unified' in harmonizer_result.lower():
            logger.info("   ✅ Data harmonization completed")
        
        # Check for quality assurance indicators
        qa_result = collected_data.get('quality_assurance', {}).get('full_result', '')
        if 'quality' in qa_result.lower() or 'assessment' in qa_result.lower():
            logger.info("   ✅ Quality assurance performed")
        
        logger.info("\n📋 NEXT STEPS:")
        logger.info(f"   1. Review detailed results in: {output_file}")
        logger.info("   2. Check pipeline_data/ directory for structured outputs")
        logger.info("   3. Verify database storage (if configured)")
        
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Data extraction failed: {e}")
        raise
    
    finally:
        # Stop the system
        await system.stop()


def main():
    """Main extraction function."""
    logger.info("🧬 Pharmaceutical Pipeline Data Extraction")
    logger.info("=" * 60)
    
    try:
        asyncio.run(extract_pipeline_data())
        
    except KeyboardInterrupt:
        logger.info("⏹️  Extraction interrupted by user")
    except Exception as e:
        logger.error(f"❌ Extraction failed: {e}")
        raise


if __name__ == "__main__":
    main()