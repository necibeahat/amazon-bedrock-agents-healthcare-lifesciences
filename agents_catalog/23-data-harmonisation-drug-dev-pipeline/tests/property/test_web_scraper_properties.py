"""Property-based tests for Web Scraper Agent."""

import json
import logging
from datetime import datetime
from typing import Dict, Any
from unittest.mock import Mock, patch

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from pydantic import HttpUrl

from src.agents.web_scraper import WebScraperAgent
from src.models.pipeline_data import ComplianceResult, RawPipelineData, SourceMetadata, ContentData
from src.storage.storage_manager import StorageManager

logger = logging.getLogger(__name__)


# Custom strategy for generating valid URLs
@st.composite
def valid_urls(draw):
    """Generate valid HTTP/HTTPS URLs."""
    protocol = draw(st.sampled_from(['http', 'https']))
    domain = draw(st.text(min_size=3, max_size=20, alphabet=st.characters(whitelist_categories=('Ll', 'Nd'))))
    tld = draw(st.sampled_from(['com', 'org', 'net', 'edu']))
    path = draw(st.text(min_size=0, max_size=30, alphabet=st.characters(whitelist_categories=('Ll', 'Nd', 'Pd'))))
    
    if path:
        url = f"{protocol}://{domain}.{tld}/{path}"
    else:
        url = f"{protocol}://{domain}.{tld}"
    
    return url


class TestWebScraperProperties:
    """Property-based tests for Web Scraper Agent."""
    
    @given(
        url=valid_urls(),
        is_allowed=st.booleans(),
        user_agent=st.text(min_size=5, max_size=50)
    )
    @settings(max_examples=20, deadline=5000, suppress_health_check=[HealthCheck.filter_too_much])
    def test_property_1_robots_txt_compliance(self, url: str, is_allowed: bool, user_agent: str):
        """Property 1: Robots.txt Compliance
        
        For any website URL being scraped, the Web_Scraper_Agent should check 
        robots.txt compliance before attempting data extraction and respect any 
        restrictions found.
        
        Validates: Requirements 1.1
        """
        # Arrange
        agent = WebScraperAgent()
        
        try:
            parsed_url = HttpUrl(url)
        except Exception:
            # Skip invalid URLs
            assume(False)
        
        mock_compliance_result = ComplianceResult(
            url=parsed_url,
            is_allowed=is_allowed,
            user_agent=user_agent
        )
        
        # Act & Assert
        with patch.object(agent.robots_checker, 'check_compliance', return_value=mock_compliance_result) as mock_check:
            result = agent.check_robots_compliance(parsed_url)
            
            # Property: Agent MUST check robots.txt compliance
            mock_check.assert_called_once_with(parsed_url)
            
            # Property: Result MUST reflect the compliance status
            assert result.is_allowed == is_allowed
            assert result.url == parsed_url
            assert result.user_agent == user_agent
    
    @given(
        url=valid_urls(),
        error_message=st.text(min_size=1, max_size=200)
    )
    @settings(max_examples=15, deadline=5000, suppress_health_check=[HealthCheck.filter_too_much])
    @pytest.mark.asyncio
    async def test_property_2_compliance_violation_handling(self, url: str, error_message: str):
        """Property 2: Compliance Violation Handling
        
        For any website that prohibits data collection via robots.txt, the 
        Web_Scraper_Agent should log the restriction and notify the user without 
        attempting extraction.
        
        Validates: Requirements 1.2
        """
        # Arrange
        agent = WebScraperAgent()
        
        try:
            parsed_url = HttpUrl(url)
        except Exception:
            # Skip invalid URLs
            assume(False)
        
        # Mock a compliance violation
        mock_compliance_result = ComplianceResult(
            url=parsed_url,
            is_allowed=False,
            user_agent="TestAgent/1.0",
            error_message=error_message
        )
        
        # Act & Assert
        with patch.object(agent.robots_checker, 'check_compliance', return_value=mock_compliance_result):
            with patch.object(agent.http_client, 'get') as mock_get:
                with pytest.raises(ValueError) as exc_info:
                    # This should raise an exception without attempting HTTP request
                    await agent._collect_single_url("TestCompany", parsed_url)
                
                # Property: Should NOT attempt HTTP request when prohibited
                mock_get.assert_not_called()
                
                # Property: Should raise exception with compliance information
                assert "Robots.txt prohibits scraping" in str(exc_info.value)
                assert str(parsed_url) in str(exc_info.value)
    
    @given(
        company=st.text(min_size=1, max_size=50),
        url=valid_urls(),
        html_content=st.text(min_size=100, max_size=2000),
        status_code=st.integers(min_value=200, max_value=299),
        headers=st.dictionaries(
            st.text(min_size=1, max_size=20), 
            st.text(min_size=1, max_size=50), 
            min_size=1, 
            max_size=3
        )
    )
    @settings(max_examples=10, deadline=10000, suppress_health_check=[HealthCheck.filter_too_much])
    @pytest.mark.asyncio
    async def test_property_3_raw_data_preservation(
        self, 
        company: str, 
        url: str, 
        html_content: str, 
        status_code: int, 
        headers: Dict[str, str]
    ):
        """Property 3: Raw Data Preservation
        
        For any collected data, the Storage_Manager should save it in JSON format 
        while preserving original structure, metadata, collection timestamp, and 
        source URL.
        
        Validates: Requirements 1.6, 1.7
        """
        # Arrange
        try:
            parsed_url = HttpUrl(url)
        except Exception:
            # Skip invalid URLs
            assume(False)
        
        # Mock storage manager
        mock_storage = Mock(spec=StorageManager)
        mock_storage.store_raw_data.return_value = Mock(success=True, record_id="test-id")
        
        agent = WebScraperAgent(storage_manager=mock_storage)
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.status_code = status_code
        mock_response.headers = headers
        
        # Mock compliance check (allow scraping)
        mock_compliance_result = ComplianceResult(
            url=parsed_url,
            is_allowed=True,
            user_agent="TestAgent/1.0"
        )
        
        # Mock extraction result
        mock_extraction_result = Mock()
        mock_extraction_result.entries = []
        mock_extraction_result.metadata = {"test": "metadata"}
        mock_extraction_result.confidence_score = 0.8
        mock_extraction_result.extraction_method = "test_method"
        mock_extraction_result.errors = []
        
        # Mock model_dump method for extraction result entries
        def mock_model_dump():
            return {
                "compound_name": "test_compound",
                "indication": "test_indication"
            }
        
        # Create mock entries with model_dump method
        mock_entry = Mock()
        mock_entry.model_dump = mock_model_dump
        mock_extraction_result.entries = [mock_entry]
        
        # Act
        with patch.object(agent.robots_checker, 'check_compliance', return_value=mock_compliance_result):
            with patch.object(agent.http_client, 'get', return_value=mock_response):
                with patch.object(agent.extractor, 'extract', return_value=mock_extraction_result):
                    with patch.object(agent.http_client, '_get_random_user_agent', return_value="TestAgent/1.0"):
                        with patch.object(agent.http_client, 'get_stats', return_value={"requests": 1}):
                            result = await agent._collect_single_url(company, parsed_url)
        
        # Assert - Verify storage was called
        mock_storage.store_raw_data.assert_called_once()
        stored_data = mock_storage.store_raw_data.call_args[0][0]
        
        # Property: Original structure MUST be preserved
        assert isinstance(stored_data, RawPipelineData)
        assert stored_data.content.raw_html == html_content
        
        # Property: Metadata MUST be preserved
        assert stored_data.source.company == company
        assert stored_data.source.url == parsed_url
        assert stored_data.source.robots_compliance is True
        
        # Property: Collection timestamp MUST be present
        assert stored_data.created_at is not None
        assert isinstance(stored_data.created_at, datetime)
        
        # Property: Source URL MUST be tracked
        assert stored_data.source.url == parsed_url
        
        # Property: Data MUST be JSON serializable (test core fields)
        try:
            # Test that the main data structure can be serialized
            test_json = {
                "id": str(stored_data.id),
                "company": stored_data.source.company,
                "url": str(stored_data.source.url),
                "html_length": len(stored_data.content.raw_html),
                "created_at": stored_data.created_at.isoformat()
            }
            json.dumps(test_json)  # This should not raise an exception
        except (TypeError, ValueError) as e:
            pytest.fail(f"Core stored data is not JSON serializable: {e}")
        
        # Property: HTTP response details MUST be preserved
        extracted_data = stored_data.content.extracted_data
        assert extracted_data["status_code"] == status_code
        assert extracted_data["headers"] == headers
        assert extracted_data["content_length"] == len(html_content)
    
    @given(
        urls=st.lists(valid_urls(), min_size=1, max_size=3)
    )
    @settings(max_examples=5, deadline=5000, suppress_health_check=[HealthCheck.filter_too_much])
    def test_property_robots_compliance_consistency(self, urls: list):
        """Property: Robots.txt compliance checking should be consistent
        
        For the same URL, multiple compliance checks should return the same result.
        """
        # Arrange
        agent = WebScraperAgent()
        
        valid_urls = []
        for url in urls:
            try:
                valid_urls.append(HttpUrl(url))
            except Exception:
                continue
        
        assume(len(valid_urls) > 0)
        
        # Mock consistent compliance results
        mock_results = {}
        for url in valid_urls:
            mock_results[str(url)] = ComplianceResult(
                url=url,
                is_allowed=True,  # Consistent result
                user_agent="TestAgent/1.0"
            )
        
        def mock_check_compliance(url):
            return mock_results[str(url)]
        
        # Act & Assert
        with patch.object(agent.robots_checker, 'check_compliance', side_effect=mock_check_compliance):
            for url in valid_urls:
                # Check multiple times
                result1 = agent.check_robots_compliance(url)
                result2 = agent.check_robots_compliance(url)
                
                # Property: Results should be consistent
                assert result1.is_allowed == result2.is_allowed
                assert result1.url == result2.url
                assert result1.user_agent == result2.user_agent
    
    @given(
        invalid_data=st.one_of(
            st.none(),
            st.text(max_size=50),  # Too short content
            st.just(""),  # Empty content
        )
    )
    @settings(max_examples=10, deadline=3000)
    def test_property_validation_robustness(self, invalid_data):
        """Property: Content validation should handle invalid data gracefully
        
        For any invalid or malformed data, the validation should fail gracefully 
        without crashing.
        """
        # Arrange
        agent = WebScraperAgent()
        
        if invalid_data is None:
            html_content = ""
        else:
            html_content = str(invalid_data)
        
        test_data = RawPipelineData(
            source=SourceMetadata(
                company="TestCompany",
                url=HttpUrl("https://example.com"),
                robots_compliance=True
            ),
            content=ContentData(
                raw_html=html_content,
                extracted_data={"pipeline_entries": []},
                parsing_method="test",
                content_hash="test_hash"
            )
        )
        
        # Act
        try:
            result = agent.validate_content(test_data)
            
            # Property: Validation should complete without crashing
            assert hasattr(result, 'is_valid')
            assert hasattr(result, 'validation_errors')
            assert hasattr(result, 'confidence_score')
            
            # Property: Invalid data should be marked as invalid
            if not html_content or len(html_content) < 100:
                assert result.is_valid is False
                assert len(result.validation_errors) > 0
            
        except Exception as e:
            pytest.fail(f"Validation should not crash on invalid data: {e}")