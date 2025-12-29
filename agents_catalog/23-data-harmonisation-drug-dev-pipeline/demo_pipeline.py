#!/usr/bin/env python3
"""
Demo script to run the complete agentic pharmaceutical pipeline.

This script demonstrates:
1. Web scraping pharmaceutical pipeline data from company websites
2. Schema analysis and unified model creation
3. Ontology mapping and semantic enrichment
4. Duplicate resolution and data harmonization
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import List

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.agents.web_scraper import WebScraperAgent
from src.agents.data_harmonizer import DataHarmonizerAgent
from src.models.pipeline_data import RawPipelineData

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('pipeline_demo.log')
    ]
)

logger = logging.getLogger(__name__)


class PipelineDemo:
    """Demonstrates the complete pharmaceutical data pipeline."""
    
    def __init__(self):
        """Initialize the demo with agents."""
        logger.info("Initializing Pharmaceutical Data Pipeline Demo")
        
        # Initialize agents (without storage for demo)
        self.web_scraper = WebScraperAgent()
        self.data_harmonizer = DataHarmonizerAgent()
        
        # Results storage
        self.raw_data_results = []
        self.harmonization_results = {}
        
        logger.info("Pipeline demo initialized successfully")
    
    async def run_complete_pipeline(self):
        """Run the complete data pipeline from collection to harmonization."""
        try:
            logger.info("=" * 60)
            logger.info("STARTING PHARMACEUTICAL DATA PIPELINE DEMO")
            logger.info("=" * 60)
            
            # Step 1: Collect raw data from pharmaceutical websites
            await self.collect_raw_data()
            
            # Step 2: Analyze schemas and create unified model
            await self.analyze_and_harmonize_data()
            
            # Step 3: Display results
            self.display_results()
            
            logger.info("=" * 60)
            logger.info("PIPELINE DEMO COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Pipeline demo failed: {e}")
            raise
    
    async def collect_raw_data(self):
        """Collect raw data from pharmaceutical company websites."""
        logger.info("Step 1: Collecting raw data from pharmaceutical websites")
        logger.info("-" * 50)
        
        try:
            # Collect data from all target companies
            result = await self.web_scraper.collect_all_pipeline_data()
            
            if result.get("success", True):  # Default to True if not specified
                self.raw_data_results = result.get("results", [])
                logger.info(f"✓ Successfully collected data from {len(self.raw_data_results)} sources")
                
                # Log collection summary
                for i, raw_data_dict in enumerate(self.raw_data_results):
                    company = raw_data_dict.get("source", {}).get("company", "Unknown")
                    pipeline_entries = raw_data_dict.get("content", {}).get("extracted_data", {}).get("pipeline_entries", [])
                    logger.info(f"  - {company}: {len(pipeline_entries)} pipeline entries extracted")
            else:
                logger.error(f"Data collection failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Failed to collect raw data: {e}")
            # Continue with demo data for demonstration
            logger.info("Using demo data for pipeline demonstration...")
            self.raw_data_results = self._create_demo_data()
    
    async def analyze_and_harmonize_data(self):
        """Analyze schemas and harmonize the collected data."""
        logger.info("Step 2: Analyzing schemas and harmonizing data")
        logger.info("-" * 50)
        
        if not self.raw_data_results:
            logger.warning("No raw data available for harmonization")
            return
        
        try:
            # Convert dictionaries back to RawPipelineData objects
            raw_data_objects = []
            for raw_data_dict in self.raw_data_results:
                try:
                    raw_data_obj = RawPipelineData(**raw_data_dict)
                    raw_data_objects.append(raw_data_obj)
                except Exception as e:
                    logger.warning(f"Failed to convert raw data dict to object: {e}")
                    continue
            
            if not raw_data_objects:
                logger.error("No valid raw data objects for harmonization")
                return
            
            # Run complete harmonization pipeline
            result = await self.data_harmonizer.harmonize_complete_pipeline(raw_data_objects)
            
            if result.get("success", False):
                self.harmonization_results = result
                logger.info("✓ Data harmonization completed successfully")
                
                # Log harmonization summary
                summary = result.get("pipeline_summary", {})
                logger.info(f"  - Original sources: {summary.get('original_sources', 0)}")
                logger.info(f"  - Common fields identified: {summary.get('common_fields_identified', 0)}")
                logger.info(f"  - Model confidence: {summary.get('model_confidence', 0):.3f}")
                logger.info(f"  - Final canonical entries: {summary.get('final_canonical_entries', 0)}")
                logger.info(f"  - Deduplication rate: {summary.get('deduplication_rate', 0):.1%}")
            else:
                logger.error(f"Data harmonization failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Failed to harmonize data: {e}")
    
    def display_results(self):
        """Display the pipeline results."""
        logger.info("Step 3: Pipeline Results Summary")
        logger.info("-" * 50)
        
        # Raw data collection results
        logger.info(f"📊 RAW DATA COLLECTION:")
        logger.info(f"   • Sources processed: {len(self.raw_data_results)}")
        
        total_entries = 0
        for raw_data_dict in self.raw_data_results:
            pipeline_entries = raw_data_dict.get("content", {}).get("extracted_data", {}).get("pipeline_entries", [])
            total_entries += len(pipeline_entries)
        
        logger.info(f"   • Total pipeline entries: {total_entries}")
        
        # Harmonization results
        if self.harmonization_results:
            logger.info(f"🔄 DATA HARMONIZATION:")
            summary = self.harmonization_results.get("pipeline_summary", {})
            
            logger.info(f"   • Common fields identified: {summary.get('common_fields_identified', 0)}")
            logger.info(f"   • Model confidence score: {summary.get('model_confidence', 0):.3f}")
            logger.info(f"   • Original entries: {summary.get('original_entries', 0)}")
            logger.info(f"   • Final canonical entries: {summary.get('final_canonical_entries', 0)}")
            logger.info(f"   • Deduplication rate: {summary.get('deduplication_rate', 0):.1%}")
            
            # Show some example unified data
            deduplicated_data = self.harmonization_results.get("deduplicated_data", {})
            canonical_entries = deduplicated_data.get("canonical_entries", [])
            
            if canonical_entries:
                logger.info(f"📋 SAMPLE HARMONIZED DATA:")
                for i, entry in enumerate(canonical_entries[:3]):  # Show first 3 entries
                    unified_data = entry.get("unified_data", {})
                    compound_name = unified_data.get("compound_name", "Unknown")
                    indication = unified_data.get("indication", "Unknown")
                    phase = unified_data.get("development_phase", "Unknown")
                    company = unified_data.get("company", "Unknown")
                    
                    logger.info(f"   {i+1}. {compound_name} ({company})")
                    logger.info(f"      Indication: {indication}")
                    logger.info(f"      Phase: {phase}")
        
        # Save results to file
        self._save_results_to_file()
    
    def _create_demo_data(self) -> List[dict]:
        """Create demo data for pipeline demonstration."""
        logger.info("Creating demo data for pipeline demonstration")
        
        from datetime import datetime
        from uuid import uuid4
        
        demo_data = []
        
        # Demo data for Merck
        merck_data = {
            "id": str(uuid4()),
            "source": {
                "company": "Merck",
                "url": "https://www.merck.com/research/product-pipeline/",
                "collected_at": datetime.utcnow().isoformat(),
                "robots_compliance": True,
                "collection_agent": "WebScraperAgent"
            },
            "content": {
                "raw_html": "<html>Demo HTML content</html>",
                "extracted_data": {
                    "pipeline_entries": [
                        {
                            "compound_name": "Pembrolizumab",
                            "indication": "Non-small cell lung cancer",
                            "development_phase": "approved",
                            "therapeutic_area": "Oncology",
                            "mechanism_of_action": "PD-1 inhibitor"
                        },
                        {
                            "compound_name": "Donanemab",
                            "indication": "Alzheimer's disease",
                            "development_phase": "phase_3",
                            "therapeutic_area": "Neurology"
                        }
                    ]
                },
                "parsing_method": "demo_extraction",
                "content_hash": "demo_hash_merck"
            },
            "metadata": {},
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Demo data for Novo Nordisk
        novo_data = {
            "id": str(uuid4()),
            "source": {
                "company": "Novo Nordisk",
                "url": "https://www.novonordisk.com/science-and-technology/r-d-pipeline.html",
                "collected_at": datetime.utcnow().isoformat(),
                "robots_compliance": True,
                "collection_agent": "WebScraperAgent"
            },
            "content": {
                "raw_html": "<html>Demo HTML content</html>",
                "extracted_data": {
                    "pipeline_entries": [
                        {
                            "compound_name": "Semaglutide",
                            "indication": "Type 2 diabetes",
                            "development_phase": "approved",
                            "therapeutic_area": "Diabetes",
                            "mechanism_of_action": "GLP-1 receptor agonist"
                        },
                        {
                            "compound_name": "Insulin icodec",
                            "indication": "Type 1 diabetes",
                            "development_phase": "phase_3",
                            "therapeutic_area": "Diabetes"
                        }
                    ]
                },
                "parsing_method": "demo_extraction",
                "content_hash": "demo_hash_novo"
            },
            "metadata": {},
            "created_at": datetime.utcnow().isoformat()
        }
        
        demo_data.extend([merck_data, novo_data])
        logger.info(f"Created demo data with {len(demo_data)} sources")
        
        return demo_data
    
    def _save_results_to_file(self):
        """Save pipeline results to JSON file."""
        try:
            from datetime import datetime
            
            results = {
                "raw_data_collection": {
                    "total_sources": len(self.raw_data_results),
                    "sources": [
                        {
                            "company": data.get("source", {}).get("company", "Unknown"),
                            "entries_count": len(data.get("content", {}).get("extracted_data", {}).get("pipeline_entries", []))
                        }
                        for data in self.raw_data_results
                    ]
                },
                "harmonization_results": self.harmonization_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            with open("pipeline_results.json", "w") as f:
                json.dump(results, f, indent=2, default=str)
            
            logger.info("✓ Results saved to pipeline_results.json")
            
        except Exception as e:
            logger.warning(f"Failed to save results to file: {e}")


async def main():
    """Main function to run the pipeline demo."""
    try:
        demo = PipelineDemo()
        await demo.run_complete_pipeline()
        
    except KeyboardInterrupt:
        logger.info("Pipeline demo interrupted by user")
    except Exception as e:
        logger.error(f"Pipeline demo failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())