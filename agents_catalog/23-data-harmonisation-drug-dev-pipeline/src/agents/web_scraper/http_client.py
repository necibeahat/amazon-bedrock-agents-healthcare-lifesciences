"""HTTP client with user-agent rotation and rate limiting."""

import asyncio
import logging
import random
import time
from typing import Dict, List, Optional

import httpx
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class RateLimitedHTTPClient:
    """HTTP client with rate limiting and user-agent rotation."""
    
    # Common user agents for pharmaceutical research
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        "PharmaAgent/1.0 (Research Bot; +https://example.com/bot)",
    ]
    
    def __init__(
        self,
        requests_per_second: float = 1.0,
        timeout: int = 30,
        max_retries: int = 3,
        custom_user_agents: Optional[List[str]] = None
    ):
        """Initialize the HTTP client.
        
        Args:
            requests_per_second: Maximum requests per second (rate limit)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            custom_user_agents: Custom user agent strings to use
        """
        self.requests_per_second = requests_per_second
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agents = custom_user_agents or self.USER_AGENTS
        
        # Rate limiting state
        self._last_request_time = 0.0
        self._request_interval = 1.0 / requests_per_second
        
        # Session for connection pooling
        self.session = requests.Session()
        
        # Request statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "rate_limited_requests": 0
        }
    
    def _get_random_user_agent(self) -> str:
        """Get a random user agent string."""
        return random.choice(self.user_agents)
    
    def _enforce_rate_limit(self):
        """Enforce rate limiting by sleeping if necessary."""
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        
        if time_since_last_request < self._request_interval:
            sleep_time = self._request_interval - time_since_last_request
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
            self.stats["rate_limited_requests"] += 1
        
        self._last_request_time = time.time()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def get(self, url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> requests.Response:
        """Make a GET request with rate limiting and retries.
        
        Args:
            url: URL to request
            headers: Additional headers to include
            **kwargs: Additional arguments to pass to requests.get
            
        Returns:
            Response object
            
        Raises:
            requests.RequestException: If request fails after retries
        """
        self._enforce_rate_limit()
        
        # Prepare headers with random user agent
        request_headers = {
            "User-Agent": self._get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        if headers:
            request_headers.update(headers)
        
        try:
            self.stats["total_requests"] += 1
            
            response = self.session.get(
                url,
                headers=request_headers,
                timeout=self.timeout,
                **kwargs
            )
            
            response.raise_for_status()
            self.stats["successful_requests"] += 1
            
            logger.debug(f"Successfully fetched {url} (status: {response.status_code})")
            return response
            
        except requests.RequestException as e:
            self.stats["failed_requests"] += 1
            logger.error(f"Request failed for {url}: {e}")
            raise
    
    async def get_async(self, url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> httpx.Response:
        """Make an async GET request with rate limiting and retries.
        
        Args:
            url: URL to request
            headers: Additional headers to include
            **kwargs: Additional arguments to pass to httpx.get
            
        Returns:
            Response object
            
        Raises:
            httpx.RequestError: If request fails after retries
        """
        # Async rate limiting
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        
        if time_since_last_request < self._request_interval:
            sleep_time = self._request_interval - time_since_last_request
            logger.debug(f"Async rate limiting: sleeping for {sleep_time:.2f} seconds")
            await asyncio.sleep(sleep_time)
            self.stats["rate_limited_requests"] += 1
        
        self._last_request_time = time.time()
        
        # Prepare headers with random user agent
        request_headers = {
            "User-Agent": self._get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        if headers:
            request_headers.update(headers)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                self.stats["total_requests"] += 1
                
                response = await client.get(
                    url,
                    headers=request_headers,
                    **kwargs
                )
                
                response.raise_for_status()
                self.stats["successful_requests"] += 1
                
                logger.debug(f"Successfully fetched {url} (status: {response.status_code})")
                return response
                
            except httpx.RequestError as e:
                self.stats["failed_requests"] += 1
                logger.error(f"Async request failed for {url}: {e}")
                raise
    
    def get_stats(self) -> Dict[str, int]:
        """Get request statistics.
        
        Returns:
            Dictionary with request statistics
        """
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset request statistics."""
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "rate_limited_requests": 0
        }
    
    def close(self):
        """Close the HTTP session."""
        self.session.close()