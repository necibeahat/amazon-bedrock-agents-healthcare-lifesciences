"""
Agent Configuration Loader
Loads AgentCore Runtime Agent ARNs from various sources (JSON file, SSM, or environment variables)
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional
import boto3


class AgentConfigLoader:
    """Load and manage AgentCore Runtime Agent ARNs"""
    
    def __init__(self, config_file: str = None, region: str = None):
        """
        Initialize the config loader
        
        Args:
            config_file: Path to agent_arns.json file (default: ../agent_arns.json)
            region: AWS region (default: from AWS_REGION env var or us-east-1)
        """
        self.region = region or os.getenv('AWS_REGION', 'us-east-1')
        
        # Default config file location
        if config_file is None:
            current_dir = Path(__file__).parent
            config_file = current_dir.parent / 'agent_arns.json'
        
        self.config_file = Path(config_file)
        self._config_cache = None
        self._ssm_client = None
    
    @property
    def ssm_client(self):
        """Lazy load SSM client"""
        if self._ssm_client is None:
            self._ssm_client = boto3.client('ssm', region_name=self.region)
        return self._ssm_client
    
    def load_from_file(self) -> Dict:
        """
        Load agent configuration from JSON file
        
        Returns:
            Dict with agent configuration
        """
        if not self.config_file.exists():
            raise FileNotFoundError(
                f"Agent configuration file not found: {self.config_file}\n"
                "Run 'cd deploy && bash load_agent_arns.sh' to generate it."
            )
        
        with open(self.config_file, 'r') as f:
            return json.load(f)
    
    def load_from_ssm(self, ssm_prefix: str = '/idp-agents') -> Dict:
        """
        Load agent configuration from SSM Parameter Store
        
        Args:
            ssm_prefix: SSM parameter prefix (default: /idp-agents)
            
        Returns:
            Dict with agent configuration
        """
        config = {
            'agents': {},
            'source': 'ssm',
            'region': self.region
        }
        
        # List all parameters under the prefix
        try:
            paginator = self.ssm_client.get_paginator('get_parameters_by_path')
            page_iterator = paginator.paginate(
                Path=ssm_prefix,
                Recursive=True,
                WithDecryption=False
            )
            
            for page in page_iterator:
                for param in page['Parameters']:
                    # Parse parameter name: /idp-agents/agent_name/arn
                    parts = param['Name'].split('/')
                    if len(parts) >= 4 and parts[-1] == 'arn':
                        agent_name = parts[-2]
                        config['agents'][agent_name] = {
                            'agent_arn': param['Value'],
                            'status': 'deployed'
                        }
            
            return config
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration from SSM: {str(e)}")
    
    def get_config(self, force_reload: bool = False, prefer_ssm: bool = False) -> Dict:
        """
        Get agent configuration, using cache if available
        
        Args:
            force_reload: Force reload from source
            prefer_ssm: Try SSM first before file
            
        Returns:
            Dict with agent configuration
        """
        if self._config_cache is not None and not force_reload:
            return self._config_cache
        
        # Try to load from preferred source
        if prefer_ssm:
            try:
                self._config_cache = self.load_from_ssm()
                return self._config_cache
            except Exception:
                pass  # Fall back to file
        
        # Load from file
        try:
            self._config_cache = self.load_from_file()
            return self._config_cache
        except FileNotFoundError:
            if not prefer_ssm:
                # Try SSM as fallback
                try:
                    self._config_cache = self.load_from_ssm()
                    return self._config_cache
                except Exception:
                    pass
            
            raise RuntimeError(
                "Could not load agent configuration from file or SSM.\n"
                "Run 'cd deploy && bash load_agent_arns.sh' to generate the configuration."
            )
    
    def get_agent_arn(self, agent_name: str, force_reload: bool = False) -> str:
        """
        Get ARN for a specific agent
        
        Args:
            agent_name: Name of the agent
            force_reload: Force reload configuration
            
        Returns:
            Agent ARN
            
        Raises:
            ValueError: If agent not found
        """
        config = self.get_config(force_reload=force_reload)
        
        if agent_name not in config.get('agents', {}):
            available = ', '.join(config.get('agents', {}).keys())
            raise ValueError(
                f"Agent '{agent_name}' not found in configuration.\n"
                f"Available agents: {available}"
            )
        
        return config['agents'][agent_name]['agent_arn']
    
    def get_agent_id(self, agent_name: str, force_reload: bool = False) -> Optional[str]:
        """
        Get ID for a specific agent (if available)
        
        Args:
            agent_name: Name of the agent
            force_reload: Force reload configuration
            
        Returns:
            Agent ID or None if not available
        """
        config = self.get_config(force_reload=force_reload)
        agent_config = config.get('agents', {}).get(agent_name, {})
        return agent_config.get('agent_id')
    
    def list_agents(self, force_reload: bool = False) -> Dict[str, str]:
        """
        List all available agents and their ARNs
        
        Args:
            force_reload: Force reload configuration
            
        Returns:
            Dict mapping agent names to ARNs
        """
        config = self.get_config(force_reload=force_reload)
        return {
            name: info['agent_arn']
            for name, info in config.get('agents', {}).items()
        }
    
    def get_account_info(self, force_reload: bool = False) -> Dict[str, str]:
        """
        Get AWS account and region information
        
        Args:
            force_reload: Force reload configuration
            
        Returns:
            Dict with account_id and region
        """
        config = self.get_config(force_reload=force_reload)
        return {
            'account_id': config.get('account_id', 'unknown'),
            'region': config.get('region', self.region)
        }


# Convenience functions for direct access
def get_agent_arn(agent_name: str, config_file: str = None, region: str = None) -> str:
    """
    Get ARN for a specific agent
    
    Args:
        agent_name: Name of the agent
        config_file: Path to agent_arns.json file (optional)
        region: AWS region (optional)
        
    Returns:
        Agent ARN
    """
    loader = AgentConfigLoader(config_file=config_file, region=region)
    return loader.get_agent_arn(agent_name)


def list_agents(config_file: str = None, region: str = None) -> Dict[str, str]:
    """
    List all available agents and their ARNs
    
    Args:
        config_file: Path to agent_arns.json file (optional)
        region: AWS region (optional)
        
    Returns:
        Dict mapping agent names to ARNs
    """
    loader = AgentConfigLoader(config_file=config_file, region=region)
    return loader.list_agents()


# Example usage
if __name__ == "__main__":
    # Create loader
    loader = AgentConfigLoader()
    
    print("=== Agent Configuration Loader ===\n")
    
    # Get account info
    try:
        account_info = loader.get_account_info()
        print(f"Account ID: {account_info['account_id']}")
        print(f"Region: {account_info['region']}\n")
    except Exception as e:
        print(f"Could not load account info: {e}\n")
    
    # List all agents
    try:
        print("Available Agents:")
        agents = loader.list_agents()
        for name, arn in agents.items():
            print(f"  • {name}")
            print(f"    ARN: {arn}")
            agent_id = loader.get_agent_id(name)
            if agent_id:
                print(f"    ID: {agent_id}")
        print()
    except Exception as e:
        print(f"Error: {e}\n")
    
    # Example: Get specific agent ARN
    try:
        extractor_arn = loader.get_agent_arn('idp_extractor_agent')
        print(f"Extractor Agent ARN: {extractor_arn}")
    except Exception as e:
        print(f"Could not get extractor agent: {e}")
