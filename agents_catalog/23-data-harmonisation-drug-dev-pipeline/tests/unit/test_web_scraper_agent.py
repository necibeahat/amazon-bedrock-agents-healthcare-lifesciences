"""Unit tests for Web Scraper Agent."""

import pytest
from unittest.mock import Mock, patch
from pydantic import HttpUrl

from src.agents.web_scraper import WebScraperAgent
from src.models.pipeline_data import ComplianceResult


class TestWebScraperAgent:
    """Test cases for WebScraperAgent."""
    
    def test_agent_initialization(self):
        """Test that the agent initializes correctly."""
        agent = WebScraperAgent()
        
        assert agent.name == "WebScraperAgent"
        assert agent.robots_checker is not None
        assert agent.http_client is not None
        assert agent.extractor is not None
        assert len(agent.target_urls) == 3
        assert "Merck" in agent.target_urls
        assert "Novo Nordisk" in agent.target_urls
        assert "Novartis" in agent.target_urls
    
    def test_robots_compliance_check(self):
        """Test robots.txt compliance checking."""
        agent = WebScraperAgent()
        
        # Mock the robots checker
        mock_result = ComplianceResult(
            url=HttpUrl("https://example.com"),
            is_allowed=True,
            user_agent="PharmaAgent/1.0"
        )
        
        with patch.object(agent.robots_checker, 'check_compliance', return_value=mock_result):
            result = agent.check_robots_compliance(HttpUrl("https://example.com"))
            
            assert result.is_allowed is True
            assert result.url == HttpUrl("https://example.com")
    
    def test_content_validation_valid_html(self):
        """Test content validation with valid HTML."""
        agent = WebScraperAgent()
        
        from src.models.pipeline_data import RawPipelineData, SourceMetadata, ContentData
        
        # Create test data with valid HTML content (longer content to pass length check)
        long_html = "<html><head><title>Test</title></head><body>" + "Valid content " * 20 + "</body></html>"
        test_data = RawPipelineData(
            source=SourceMetadata(
                company="TestCompany",
                url=HttpUrl("https://example.com"),
                robots_compliance=True
            ),
            content=ContentData(
                raw_html=long_html,
                extracted_data={
                    "pipeline_entries": [{"compound_name": "Test-123"}],
                    "extraction_confidence": 0.8  # Add confidence score
                },
                parsing_method="test",
                content_hash="test_hash"
            )
        )
        
        result = agent.validate_content(test_data)
        
        assert result.is_valid is True
        assert len(result.validation_errors) == 0
        assert result.confidence_score > 0.5
    
    def test_content_validation_empty_html(self):
        """Test content validation with empty HTML."""
        agent = WebScraperAgent()
        
        from src.models.pipeline_data import RawPipelineData, SourceMetadata, ContentData
        
        # Create test data with empty HTML content
        test_data = RawPipelineData(
            source=SourceMetadata(
                company="TestCompany",
                url=HttpUrl("https://example.com"),
                robots_compliance=True
            ),
            content=ContentData(
                raw_html="",
                extracted_data={"pipeline_entries": []},
                parsing_method="test",
                content_hash="test_hash"
            )
        )
        
        result = agent.validate_content(test_data)
        
        assert result.is_valid is False
        assert "Empty HTML content" in result.validation_errors
        assert "No pipeline entries extracted from content" in result.validation_errors
    
    def test_title_extraction(self):
        """Test HTML title extraction."""
        agent = WebScraperAgent()
        
        html_with_title = "<html><head><title>Test Pipeline Page</title></head><body></body></html>"
        title = agent._extract_title(html_with_title)
        
        assert title == "Test Pipeline Page"
        
        html_without_title = "<html><head></head><body></body></html>"
        title = agent._extract_title(html_without_title)
        
        assert title == ""
    
    def test_store_raw_data_without_storage_manager(self):
        """Test storing data without a storage manager."""
        agent = WebScraperAgent()  # No storage manager provided
        
        from src.models.pipeline_data import RawPipelineData, SourceMetadata, ContentData
        
        test_data = RawPipelineData(
            source=SourceMetadata(
                company="TestCompany",
                url=HttpUrl("https://example.com"),
                robots_compliance=True
            ),
            content=ContentData(
                raw_html="<html></html>",
                extracted_data={},
                parsing_method="test",
                content_hash="test_hash"
            )
        )
        
        result = agent.store_raw_data(test_data)
        
        assert result.success is False
        assert "No storage manager configured" in result.error_message
    
    def test_store_raw_data_with_storage_manager(self):
        """Test storing data with a storage manager."""
        # Mock storage manager
        mock_storage = Mock()
        mock_storage.store_raw_data.return_value = Mock(success=True, record_id="test-id")
        
        agent = WebScraperAgent(storage_manager=mock_storage)
        
        from src.models.pipeline_data import RawPipelineData, SourceMetadata, ContentData
        
        test_data = RawPipelineData(
            source=SourceMetadata(
                company="TestCompany",
                url=HttpUrl("https://example.com"),
                robots_compliance=True
            ),
            content=ContentData(
                raw_html="<html></html>",
                extracted_data={},
                parsing_method="test",
                content_hash="test_hash"
            )
        )
        
        result = agent.store_raw_data(test_data)
        
        assert result.success is True
        mock_storage.store_raw_data.assert_called_once_with(test_data)
    
    def test_check_compliance_for_url(self):
        """Test the check_compliance_for_url method."""
        agent = WebScraperAgent()
        
        # Mock the robots checker
        mock_result = ComplianceResult(
            url=HttpUrl("https://example.com"),
            is_allowed=True,
            user_agent="PharmaAgent/1.0"
        )
        
        with patch.object(agent.robots_checker, 'check_compliance', return_value=mock_result):
            result = agent.check_compliance_for_url("https://example.com")
            
            assert result["action"] == "check_compliance"
            assert result["url"] == "https://example.com"
            assert result["compliance"]["is_allowed"] is True
    
    @pytest.mark.asyncio
    async def test_collect_company_data_unknown_company(self):
        """Test collecting data from an unknown company."""
        agent = WebScraperAgent()
        
        result = await agent.collect_company_data("UnknownCompany")
        
        assert "error" in result
        assert "Unknown company" in result["error"]
        assert "UnknownCompany" in result["error"]
    
    @pytest.mark.asyncio
    async def test_collect_all_pipeline_data_structure(self):
        """Test the structure of collect_all_pipeline_data response."""
        agent = WebScraperAgent()
        
        # Mock the _collect_single_url method to avoid actual HTTP requests
        with patch.object(agent, '_collect_single_url') as mock_collect:
            mock_collect.side_effect = Exception("Mocked error")
            
            result = await agent.collect_all_pipeline_data()
            
            assert result["action"] == "collect_all_data"
            assert "results" in result
            assert "errors" in result
            assert "total_collected" in result
            assert "total_errors" in result
            assert result["total_errors"] == 3  # Should have 3 errors for 3 companies