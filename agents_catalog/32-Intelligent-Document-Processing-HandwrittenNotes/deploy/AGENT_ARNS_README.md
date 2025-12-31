# Agent ARN Persistence Guide

This guide explains how to automatically load and persist AgentCore Runtime Agent ARNs for the IDP multi-agent system.

## Overview

When you deploy agents to Amazon Bedrock AgentCore Runtime, each agent is assigned a unique ARN (Amazon Resource Name). This system provides tools to:

1. **Automatically discover** deployed agent ARNs
2. **Persist** them to a JSON configuration file
3. **Store** them in AWS Systems Manager Parameter Store (optional)
4. **Load** them easily in your Python applications

## Quick Start

### 1. Deploy Your Agents

First, deploy your agents using the deployment scripts:

```bash
cd deploy
bash deploy_all_agents.sh
```

### 2. Load and Persist Agent ARNs

After deployment, run the ARN loader script:

```bash
cd deploy
bash load_agent_arns.sh
```

This will:
- Scan the `.bedrock_agentcore.yaml` file for deployed agents
- Extract agent IDs and ARNs
- Save them to `agent_arns.json` in the project root
- Optionally store them in AWS SSM Parameter Store

### 3. Use Agent ARNs in Your Code

#### Python Usage

```python
from agent.agent_config_loader import AgentConfigLoader

# Create loader
loader = AgentConfigLoader()

# Get specific agent ARN
extractor_arn = loader.get_agent_arn('idp_extractor_agent')
print(f"Extractor ARN: {extractor_arn}")

# List all agents
agents = loader.list_agents()
for name, arn in agents.items():
    print(f"{name}: {arn}")

# Get account info
account_info = loader.get_account_info()
print(f"Account: {account_info['account_id']}")
print(f"Region: {account_info['region']}")
```

#### Bash Usage

```bash
# Get specific agent ARN
EXTRACTOR_ARN=$(cat agent_arns.json | jq -r '.agents.idp_extractor_agent.agent_arn')

# List all agents
cat agent_arns.json | jq -r '.agents | keys[]'

# Get from SSM (if stored)
aws ssm get-parameter \
  --name /idp-agents/idp_extractor_agent/arn \
  --query Parameter.Value \
  --output text
```

## File Structure

```
agents_catalog/32-Intelligent-Document-Processing-HandwrittenNotes/
├── agent_arns.json                    # Generated: Agent ARN configuration
├── agent/
│   ├── .bedrock_agentcore.yaml        # Source: AgentCore deployment config
│   └── agent_config_loader.py         # Utility: Python loader class
└── deploy/
    ├── load_agent_arns.sh             # Script: ARN discovery and persistence
    ├── deploy_all_agents.sh           # Script: Deploy all agents
    └── AGENT_ARNS_README.md           # This file
```

## Configuration File Format

The `agent_arns.json` file has the following structure:

```json
{
  "account_id": "774305571746",
  "region": "us-east-1",
  "agents": {
    "idp_extractor_agent": {
      "agent_id": "idp_extractor_agent-ABC123XYZ",
      "agent_arn": "arn:aws:bedrock-agentcore:us-east-1:774305571746:runtime/idp_extractor_agent-ABC123XYZ",
      "status": "deployed"
    },
    "idp_database_agent": {
      "agent_id": "idp_database_agent-DEF456UVW",
      "agent_arn": "arn:aws:bedrock-agentcore:us-east-1:774305571746:runtime/idp_database_agent-DEF456UVW",
      "status": "deployed"
    },
    "idp_quality_check_agent": {
      "agent_id": "idp_quality_check_agent-GHI789RST",
      "agent_arn": "arn:aws:bedrock-agentcore:us-east-1:774305571746:runtime/idp_quality_check_agent-GHI789RST",
      "status": "deployed"
    }
  },
  "last_updated": "2025-12-30T12:00:00Z"
}
```

## SSM Parameter Store

Agent ARNs are also stored in AWS Systems Manager Parameter Store for centralized access:

| Parameter Name | Value |
|---------------|-------|
| `/idp-agents/idp_extractor_agent/arn` | Agent ARN |
| `/idp-agents/idp_database_agent/arn` | Agent ARN |
| `/idp-agents/idp_quality_check_agent/arn` | Agent ARN |

### Benefits of SSM Storage

1. **Centralized Configuration**: Access from any AWS service
2. **Version Control**: Track changes to agent deployments
3. **Security**: IAM-based access control
4. **No Local Files**: Works in Lambda, ECS, etc.

## Python API Reference

### AgentConfigLoader Class

```python
class AgentConfigLoader:
    def __init__(self, config_file: str = None, region: str = None)
    
    # Load configuration
    def get_config(self, force_reload: bool = False, prefer_ssm: bool = False) -> Dict
    
    # Get agent information
    def get_agent_arn(self, agent_name: str, force_reload: bool = False) -> str
    def get_agent_id(self, agent_name: str, force_reload: bool = False) -> Optional[str]
    def list_agents(self, force_reload: bool = False) -> Dict[str, str]
    
    # Get account information
    def get_account_info(self, force_reload: bool = False) -> Dict[str, str]
    
    # Load from specific sources
    def load_from_file(self) -> Dict
    def load_from_ssm(self, ssm_prefix: str = '/idp-agents') -> Dict
```

### Convenience Functions

```python
# Quick access functions
from agent.agent_config_loader import get_agent_arn, list_agents

# Get specific ARN
arn = get_agent_arn('idp_extractor_agent')

# List all agents
agents = list_agents()
```

## Advanced Usage

### Loading from SSM Only

```python
loader = AgentConfigLoader()
config = loader.load_from_ssm()
```

### Force Reload (Skip Cache)

```python
loader = AgentConfigLoader()
arn = loader.get_agent_arn('idp_extractor_agent', force_reload=True)
```

### Custom Config File Location

```python
loader = AgentConfigLoader(config_file='/path/to/custom_config.json')
```

### Environment Variables

The loader respects these environment variables:

- `AWS_REGION`: AWS region (default: us-east-1)
- Standard AWS SDK environment variables (AWS_ACCESS_KEY_ID, etc.)

## Troubleshooting

### "Agent configuration file not found"

**Solution**: Run the load script to generate the configuration:

```bash
cd deploy
bash load_agent_arns.sh
```

### "Agent not found in configuration"

**Possible causes**:
1. Agent not yet deployed
2. Configuration file outdated

**Solution**: Redeploy the agent and reload ARNs:

```bash
cd deploy
bash deploy_extractor_agent.sh  # Or deploy_all_agents.sh
bash load_agent_arns.sh
```

### "Could not save to SSM"

**Possible causes**:
1. Insufficient IAM permissions
2. Parameter doesn't exist

**Solution**: Ensure your AWS credentials have `ssm:PutParameter` permission:

```json
{
  "Effect": "Allow",
  "Action": [
    "ssm:PutParameter",
    "ssm:GetParameter",
    "ssm:GetParametersByPath"
  ],
  "Resource": "arn:aws:ssm:*:*:parameter/idp-agents/*"
}
```

## Integration Examples

### Streamlit Application

```python
import streamlit as st
from agent.agent_config_loader import AgentConfigLoader

# Initialize loader
@st.cache_resource
def get_agent_loader():
    return AgentConfigLoader()

loader = get_agent_loader()

# Display available agents
st.sidebar.header("Available Agents")
agents = loader.list_agents()
for name, arn in agents.items():
    st.sidebar.text(f"✓ {name}")
```

### Lambda Function

```python
import os
from agent.agent_config_loader import AgentConfigLoader

def lambda_handler(event, context):
    # Use SSM for Lambda (no local file system)
    loader = AgentConfigLoader(region=os.environ.get('AWS_REGION'))
    config = loader.load_from_ssm()
    
    extractor_arn = loader.get_agent_arn('idp_extractor_agent')
    
    # Use the ARN to invoke the agent
    # ...
```

### CI/CD Pipeline

```bash
#!/bin/bash
# In your deployment pipeline

# Deploy agents
cd deploy
bash deploy_all_agents.sh

# Load and persist ARNs
bash load_agent_arns.sh

# Upload config to S3 (for distribution)
aws s3 cp ../agent_arns.json s3://my-config-bucket/idp/
```

## Best Practices

1. **Run load_agent_arns.sh after every deployment** to keep configuration current
2. **Store agent_arns.json in version control** (if ARNs are not sensitive in your use case)
3. **Use SSM for production environments** for better security and centralized management
4. **Cache the configuration** in your application to reduce file I/O and API calls
5. **Handle missing configurations gracefully** with try-except blocks

## Maintenance

### Updating ARNs After Redeployment

When you redeploy an agent, its ARN changes. Always reload:

```bash
cd deploy
bash deploy_extractor_agent.sh
bash load_agent_arns.sh
```

### Cleaning Up Old Agents

Remove entries from SSM if an agent is deleted:

```bash
aws ssm delete-parameter --name /idp-agents/old_agent_name/arn
```

## See Also

- [DEPLOYMENT_README.md](DEPLOYMENT_README.md) - Full deployment guide
- [../README.md](../README.md) - Project overview
- [AWS Systems Manager Parameter Store Documentation](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
