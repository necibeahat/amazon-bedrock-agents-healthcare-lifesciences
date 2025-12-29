"""Robots.txt compliance checker for ethical web scraping."""

import logging
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from pydantic import HttpUrl

from ...models.pipeline_data import ComplianceResult

logger = logging.getLogger(__name__)


class RobotsChecker:
    """Handles robots.txt compliance checking and enforcement."""
    
    def __init__(self, user_agent: str = "PharmaAgent/1.0", timeout: int = 10):
        """Initialize the robots checker.
        
        Args:
            user_agent: User agent string to use for compliance checking
            timeout: Timeout in seconds for HTTP requests
        """
        self.user_agent = user_agent
        self.timeout = timeout
        self._cache = {}  # Simple cache for robots.txt files
    
    def check_compliance(self, url: HttpUrl) -> ComplianceResult:
        """Check if scraping is allowed for the given URL.
        
        Args:
            url: URL to check for robots.txt compliance
            
        Returns:
            ComplianceResult with compliance status and details
        """
        try:
            parsed_url = urlparse(str(url))
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            robots_url = urljoin(base_url, "/robots.txt")
            
            # Check cache first
            if robots_url in self._cache:
                rp = self._cache[robots_url]
            else:
                rp = self._fetch_robots_txt(robots_url)
                self._cache[robots_url] = rp
            
            if rp is None:
                # No robots.txt found, assume allowed
                logger.info(f"No robots.txt found for {base_url}, assuming allowed")
                return ComplianceResult(
                    url=url,
                    is_allowed=True,
                    robots_txt_url=None,
                    user_agent=self.user_agent
                )
            
            # Check if the URL is allowed for our user agent
            is_allowed = rp.can_fetch(self.user_agent, str(url))
            
            return ComplianceResult(
                url=url,
                is_allowed=is_allowed,
                robots_txt_url=HttpUrl(robots_url),
                user_agent=self.user_agent
            )
            
        except Exception as e:
            logger.error(f"Error checking robots.txt compliance for {url}: {e}")
            return ComplianceResult(
                url=url,
                is_allowed=False,  # Conservative approach: deny on error
                user_agent=self.user_agent,
                error_message=str(e)
            )
    
    def _fetch_robots_txt(self, robots_url: str) -> Optional[RobotFileParser]:
        """Fetch and parse robots.txt file.
        
        Args:
            robots_url: URL of the robots.txt file
            
        Returns:
            RobotFileParser instance or None if not found/error
        """
        try:
            response = requests.get(
                robots_url,
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent}
            )
            
            if response.status_code == 404:
                logger.info(f"No robots.txt found at {robots_url}")
                return None
            
            response.raise_for_status()
            
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            # Parse the content manually since set_url + read doesn't work with content
            rp_manual = RobotFileParser()
            rp_manual.set_url(robots_url)
            
            # Split content into lines and feed to parser
            for line in response.text.splitlines():
                rp_manual.read()
            
            # Use the requests content directly
            rp_content = RobotFileParser()
            rp_content.set_url(robots_url)
            
            # Create a temporary file-like object from the content
            import io
            content_file = io.StringIO(response.text)
            lines = content_file.readlines()
            
            # Parse manually
            rp_final = RobotFileParser()
            rp_final.set_url(robots_url)
            
            # Use the built-in method with content
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(response.text)
                f.flush()
                rp_final.read()
                
            # Simpler approach: create parser and feed content
            rp_simple = RobotFileParser()
            rp_simple.set_url(robots_url)
            
            # Parse the response text directly
            import urllib.robotparser
            rp_working = urllib.robotparser.RobotFileParser()
            rp_working.set_url(robots_url)
            
            # Use StringIO to simulate file reading
            content_lines = response.text.splitlines()
            
            # Manual parsing approach
            class SimpleRobotsParser:
                def __init__(self, content: str, url: str):
                    self.url = url
                    self.rules = self._parse_content(content)
                
                def _parse_content(self, content: str):
                    rules = {'*': {'allow': [], 'disallow': []}}
                    current_agent = '*'
                    
                    for line in content.splitlines():
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        if line.lower().startswith('user-agent:'):
                            current_agent = line.split(':', 1)[1].strip()
                            if current_agent not in rules:
                                rules[current_agent] = {'allow': [], 'disallow': []}
                        elif line.lower().startswith('disallow:'):
                            path = line.split(':', 1)[1].strip()
                            rules[current_agent]['disallow'].append(path)
                        elif line.lower().startswith('allow:'):
                            path = line.split(':', 1)[1].strip()
                            rules[current_agent]['allow'].append(path)
                    
                    return rules
                
                def can_fetch(self, user_agent: str, url: str) -> bool:
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    path = parsed.path or '/'
                    
                    # Check specific user agent rules first
                    if user_agent in self.rules:
                        return self._check_path_allowed(path, self.rules[user_agent])
                    
                    # Fall back to wildcard rules
                    if '*' in self.rules:
                        return self._check_path_allowed(path, self.rules['*'])
                    
                    return True  # Default allow if no rules
                
                def _check_path_allowed(self, path: str, rules: dict) -> bool:
                    # Check disallow rules first
                    for disallow_path in rules['disallow']:
                        if not disallow_path:  # Empty disallow means disallow nothing
                            continue
                        if path.startswith(disallow_path):
                            # Check if there's a more specific allow rule
                            for allow_path in rules['allow']:
                                if path.startswith(allow_path) and len(allow_path) > len(disallow_path):
                                    return True
                            return False
                    
                    return True  # Default allow
            
            # Use our simple parser
            simple_parser = SimpleRobotsParser(response.text, robots_url)
            
            # Wrap it to match RobotFileParser interface
            class RobotsParserWrapper:
                def __init__(self, parser):
                    self._parser = parser
                
                def can_fetch(self, user_agent: str, url: str) -> bool:
                    return self._parser.can_fetch(user_agent, url)
            
            return RobotsParserWrapper(simple_parser)
            
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch robots.txt from {robots_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing robots.txt from {robots_url}: {e}")
            return None