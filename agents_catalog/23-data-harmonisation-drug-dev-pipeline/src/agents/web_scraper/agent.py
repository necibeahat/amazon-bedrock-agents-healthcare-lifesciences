"""Web Scraper Agent implementation using Strands framework."""

import hashlib
import logging
from typing import Dict, List, Optional

from pydantic import HttpUrl
from strands import Agent

from ...models.pipeline_data import (
    ComplianceResult,
    ContentData,
    RawPipelineData,
    SourceMetadata,
    StorageResult,
    ValidationResult,
)
from ...storage.storage_manager import StorageManager
from .extractors import AdaptiveExtractor
from .http_client import RateLimitedHTTPClient
from .robots_checker import RobotsChecker

logger = logging.getLogger(__name__)


class WebScraperAgent:
    """Web Scraper Agent for collecting pharmaceutical pipeline data."""
    
    def __init__(self, storage_manager: Optional[StorageManager] = None, **kwargs):
        """Initialize the Web Scraper Agent.
        
        Args:
            storage_manager: Storage manager instance for data persistence
            **kwargs: Additional arguments for configuration
        """
        # Set default agent configuration
        self.name = kwargs.get('name', 'WebScraperAgent')
        self.description = kwargs.get('description', 'Collects pharmaceutical pipeline data from company websites with ethical compliance')
        
        # Initialize components
        self.robots_checker = RobotsChecker()
        self.http_client = RateLimitedHTTPClient(
            requests_per_second=0.5,  # Conservative rate limiting
            timeout=30,
            max_retries=3
        )
        self.extractor = AdaptiveExtractor()
        self.storage_manager = storage_manager
        
        # Target pharmaceutical companies and their pipeline URLs
        self.target_urls = {
            "Merck": "https://www.merck.com/research/product-pipeline/",
            "Novo Nordisk": "https://www.novonordisk.com/science-and-technology/r-d-pipeline.html",
            "Novartis": "https://www.novartis.com/research-development/novartis-pipeline?page=0"
        }
        
        logger.info(f"Initialized {self.name} with {len(self.target_urls)} target URLs")
    
    async def collect_all_pipeline_data(self) -> Dict:
        """Collect pipeline data from all target companies.
        
        Returns:
            Dictionary with collection results
        """
        results = []
        errors = []
        
        for company, url in self.target_urls.items():
            try:
                logger.info(f"Collecting data from {company}: {url}")
                result = await self._collect_single_url(company, HttpUrl(url))
                results.append(result)
                
            except Exception as e:
                error_msg = f"Failed to collect data from {company}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        return {
            "action": "collect_all_data",
            "results": [result.model_dump() for result in results],
            "errors": errors,
            "total_collected": len(results),
            "total_errors": len(errors)
        }
    
    async def collect_company_data(self, company: str) -> Dict:
        """Collect pipeline data from a specific company.
        
        Args:
            company: Company name
            
        Returns:
            Dictionary with collection result
        """
        if company not in self.target_urls:
            return {
                "error": f"Unknown company: {company}. Available: {list(self.target_urls.keys())}"
            }
        
        try:
            url = self.target_urls[company]
            logger.info(f"Collecting data from {company}: {url}")
            result = await self._collect_single_url(company, HttpUrl(url))
            
            return {
                "action": "collect_company_data",
                "company": company,
                "result": result.model_dump()
            }
            
        except Exception as e:
            error_msg = f"Failed to collect data from {company}: {e}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    def check_compliance_for_url(self, url: str) -> Dict:
        """Check robots.txt compliance for a URL without collecting data.
        
        Args:
            url: URL to check
            
        Returns:
            Dictionary with compliance result
        """
        try:
            compliance_result = self.check_robots_compliance(HttpUrl(url))
            
            return {
                "action": "check_compliance",
                "url": url,
                "compliance": compliance_result.model_dump()
            }
            
        except Exception as e:
            error_msg = f"Failed to check compliance for {url}: {e}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    async def _collect_single_url(self, company: str, url: HttpUrl) -> RawPipelineData:
        """Collect data from a single URL.
        
        Args:
            company: Company name
            url: URL to collect from
            
        Returns:
            RawPipelineData with collected information
        """
        # Check robots.txt compliance first
        compliance_result = self.check_robots_compliance(url)
        
        if not compliance_result.is_allowed:
            logger.warning(f"Robots.txt prohibits scraping {url}")
            raise ValueError(f"Robots.txt prohibits scraping {url}: {compliance_result.error_message}")
        
        # Fetch the content
        response = self.http_client.get(str(url))
        raw_html = response.text
        
        # Create content hash for deduplication
        content_hash = hashlib.sha256(raw_html.encode()).hexdigest()
        
        # Extract pipeline data using adaptive extraction
        extraction_result = self.extractor.extract(company, raw_html)
        
        # Enhanced content extraction with pipeline data
        extracted_data = {
            "title": self._extract_title(raw_html),
            "content_length": len(raw_html),
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "pipeline_entries": [entry.model_dump() for entry in extraction_result.entries],
            "extraction_metadata": extraction_result.metadata,
            "extraction_confidence": extraction_result.confidence_score,
            "extraction_method": extraction_result.extraction_method,
            "extraction_errors": extraction_result.errors
        }
        
        # Create data structures
        source_metadata = SourceMetadata(
            company=company,
            url=url,
            robots_compliance=compliance_result.is_allowed
        )
        
        content_data = ContentData(
            raw_html=raw_html,
            extracted_data=extracted_data,
            parsing_method=extraction_result.extraction_method,
            content_hash=content_hash
        )
        
        # Basic validation
        validation_result = self.validate_content(
            RawPipelineData(
                source=source_metadata,
                content=content_data
            )
        )
        
        # Create the complete raw pipeline data object
        raw_pipeline_data = RawPipelineData(
            source=source_metadata,
            content=content_data,
            validation_status=validation_result,
            metadata={
                "user_agent": self.http_client._get_random_user_agent(),
                "request_stats": self.http_client.get_stats()
            }
        )
        
        # Store the raw data if storage manager is available
        if self.storage_manager:
            storage_result = self.store_raw_data(raw_pipeline_data)
            raw_pipeline_data.metadata["storage_result"] = storage_result.model_dump()
        
        return raw_pipeline_data
    
    def check_robots_compliance(self, url: HttpUrl) -> ComplianceResult:
        """Check robots.txt compliance for a URL.
        
        Args:
            url: URL to check
            
        Returns:
            ComplianceResult with compliance status
        """
        return self.robots_checker.check_compliance(url)
    
    def store_raw_data(self, data: RawPipelineData) -> StorageResult:
        """Store raw pipeline data using the storage manager.
        
        Args:
            data: Raw pipeline data to store
            
        Returns:
            StorageResult with operation status
        """
        if not self.storage_manager:
            logger.warning("No storage manager configured, cannot store data")
            return StorageResult(
                success=False,
                error_message="No storage manager configured"
            )
        
        try:
            return self.storage_manager.store_raw_data(data)
        except Exception as e:
            logger.error(f"Failed to store raw data: {e}")
            return StorageResult(
                success=False,
                error_message=str(e)
            )
    
    def validate_content(self, data: RawPipelineData) -> ValidationResult:
        """Validate collected content data.
        
        Args:
            data: Raw pipeline data to validate
            
        Returns:
            ValidationResult with validation status
        """
        errors = []
        
        # Check if HTML content is present
        if not data.content.raw_html.strip():
            errors.append("Empty HTML content")
        
        # Check if content looks like HTML
        if not data.content.raw_html.strip().startswith(('<html', '<!DOCTYPE', '<!doctype')):
            if '<html' not in data.content.raw_html.lower():
                errors.append("Content does not appear to be HTML")
        
        # Check content length
        if len(data.content.raw_html) < 100:
            errors.append("Content too short (less than 100 characters)")
        
        # Check for common error indicators
        error_indicators = ['404', 'not found', 'error', 'forbidden', 'access denied']
        content_lower = data.content.raw_html.lower()
        for indicator in error_indicators:
            if indicator in content_lower and len(data.content.raw_html) < 5000:
                errors.append(f"Content may contain error: {indicator}")
        
        # Validate pipeline data extraction
        pipeline_entries = data.content.extracted_data.get("pipeline_entries", [])
        extraction_confidence = data.content.extracted_data.get("extraction_confidence", 0.0)
        extraction_errors = data.content.extracted_data.get("extraction_errors", [])
        
        # Add extraction errors to validation errors
        errors.extend(extraction_errors)
        
        # Check if we found any pipeline data
        if not pipeline_entries:
            errors.append("No pipeline entries extracted from content")
        else:
            # Validate pipeline entries
            valid_entries = 0
            for entry in pipeline_entries:
                if entry.get("compound_name") or entry.get("indication"):
                    valid_entries += 1
            
            if valid_entries == 0:
                errors.append("No valid pipeline entries found (missing compound names and indications)")
            elif valid_entries < len(pipeline_entries) * 0.5:
                errors.append(f"Low quality pipeline data: only {valid_entries}/{len(pipeline_entries)} entries have basic information")
        
        # Check extraction confidence
        if extraction_confidence < 0.3:
            errors.append(f"Low extraction confidence: {extraction_confidence:.2f}")
        
        # Calculate overall confidence score
        confidence_score = 1.0
        if errors:
            # Base confidence from extraction
            confidence_score = max(0.1, extraction_confidence)
            # Reduce based on validation errors
            confidence_score = max(0.0, confidence_score - (len(errors) * 0.1))
        else:
            # Use extraction confidence if no validation errors
            confidence_score = max(0.7, extraction_confidence)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            validation_errors=errors,
            confidence_score=confidence_score
        )
    
    def _extract_title(self, html: str) -> str:
        """Extract title from HTML content.
        
        Args:
            html: HTML content
            
        Returns:
            Extracted title or empty string
        """
        try:
            import re
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            if title_match:
                return title_match.group(1).strip()
        except Exception as e:
            logger.debug(f"Failed to extract title: {e}")
        
        return ""
    
    def __del__(self):
        """Cleanup resources."""
        if hasattr(self, 'http_client'):
            self.http_client.close()