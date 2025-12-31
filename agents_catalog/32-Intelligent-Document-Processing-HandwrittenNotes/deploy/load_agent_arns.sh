#!/bin/bash

# Script to load AgentCore Runtime Agent ARNs and persist them
# This script discovers all deployed AgentCore agents and saves their ARNs to a config file

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONFIG_FILE="../agent_arns.json"
SSM_PARAM_PREFIX="/idp-agents"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Loading AgentCore Runtime Agent ARNs${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}Warning: jq not found. Installing via brew...${NC}"
    brew install jq 2>/dev/null || {
        echo -e "${RED}Error: Could not install jq. Please install it manually.${NC}"
        exit 1
    }
fi

# Get AWS account ID and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)

if [ -z "$AWS_REGION" ]; then
    AWS_REGION="us-east-1"
    echo -e "${YELLOW}No region configured, defaulting to us-east-1${NC}"
fi

echo -e "${GREEN}✓ AWS Account ID: $AWS_ACCOUNT_ID${NC}"
echo -e "${GREEN}✓ AWS Region: $AWS_REGION${NC}"
echo ""

# Function to get agent ARN from bedrock-agentcore control plane
get_agent_arn() {
    local agent_name=$1
    echo -e "${YELLOW}Checking for agent: $agent_name${NC}"
    
    # Try to get agent info from the bedrock-agentcore.yaml if it exists
    if [ -f "../agent/.bedrock_agentcore.yaml" ]; then
        # Parse YAML to extract agent ARN (basic grep-based parsing)
        local arn=$(grep -A 20 "agents:" ../agent/.bedrock_agentcore.yaml | grep "agent_arn:" | head -1 | awk '{print $2}')
        if [ ! -z "$arn" ]; then
            echo -e "${GREEN}  ✓ Found ARN in .bedrock_agentcore.yaml: $arn${NC}"
            echo "$arn"
            return 0
        fi
    fi
    
    # If not found in config, try to list agents using AWS CLI
    # Note: bedrock-agentcore APIs might not be available via standard CLI yet
    # In that case, we'll need to get it from the deployment output
    echo -e "${YELLOW}  ! ARN not found in config file${NC}"
    return 1
}

# Initialize JSON structure
echo "{" > "$CONFIG_FILE"
echo "  \"account_id\": \"$AWS_ACCOUNT_ID\"," >> "$CONFIG_FILE"
echo "  \"region\": \"$AWS_REGION\"," >> "$CONFIG_FILE"
echo "  \"agents\": {" >> "$CONFIG_FILE"

# Agent names to look for
AGENT_NAMES=("idp_extractor_agent" "idp_database_agent" "idp_quality_check_agent")
AGENT_COUNT=${#AGENT_NAMES[@]}

echo -e "${BLUE}Discovering AgentCore Runtime Agents...${NC}"
echo ""

# Track how many agents we found
FOUND_COUNT=0

for i in "${!AGENT_NAMES[@]}"; do
    AGENT_NAME="${AGENT_NAMES[$i]}"
    echo -e "${YELLOW}[$((i+1))/$AGENT_COUNT] Processing $AGENT_NAME...${NC}"
    
    # Check if the agent has a .bedrock_agentcore.yaml file in its directory
    AGENT_CONFIG_FILE="../agent/.bedrock_agentcore.yaml"
    
    if [ -f "$AGENT_CONFIG_FILE" ]; then
        # Extract agent_id and agent_arn from YAML
        AGENT_ID=$(grep -A 30 "$AGENT_NAME:" "$AGENT_CONFIG_FILE" | grep "agent_id:" | head -1 | awk '{print $2}')
        AGENT_ARN=$(grep -A 30 "$AGENT_NAME:" "$AGENT_CONFIG_FILE" | grep "agent_arn:" | head -1 | awk '{print $2}')
        
        if [ ! -z "$AGENT_ARN" ] && [ ! -z "$AGENT_ID" ]; then
            echo -e "${GREEN}  ✓ Found agent ID: $AGENT_ID${NC}"
            echo -e "${GREEN}  ✓ Found agent ARN: $AGENT_ARN${NC}"
            
            # Add to JSON (add comma if not the first agent)
            if [ $FOUND_COUNT -gt 0 ]; then
                echo "," >> "$CONFIG_FILE"
            fi
            
            echo "    \"$AGENT_NAME\": {" >> "$CONFIG_FILE"
            echo "      \"agent_id\": \"$AGENT_ID\"," >> "$CONFIG_FILE"
            echo "      \"agent_arn\": \"$AGENT_ARN\"," >> "$CONFIG_FILE"
            echo "      \"status\": \"deployed\"" >> "$CONFIG_FILE"
            echo -n "    }" >> "$CONFIG_FILE"
            
            FOUND_COUNT=$((FOUND_COUNT + 1))
            
            # Optionally save to SSM Parameter Store
            SSM_PARAM_NAME="$SSM_PARAM_PREFIX/$AGENT_NAME/arn"
            echo -e "${YELLOW}  Saving to SSM: $SSM_PARAM_NAME${NC}"
            aws ssm put-parameter \
                --name "$SSM_PARAM_NAME" \
                --value "$AGENT_ARN" \
                --type "String" \
                --overwrite \
                --region "$AWS_REGION" 2>/dev/null || echo -e "${YELLOW}    ! Could not save to SSM (parameter might not exist or insufficient permissions)${NC}"
        else
            echo -e "${RED}  ✗ Agent not found or not deployed yet${NC}"
        fi
    else
        echo -e "${RED}  ✗ Config file not found: $AGENT_CONFIG_FILE${NC}"
    fi
    echo ""
done

# Close JSON structure
echo "" >> "$CONFIG_FILE"
echo "  }," >> "$CONFIG_FILE"
echo "  \"last_updated\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\"" >> "$CONFIG_FILE"
echo "}" >> "$CONFIG_FILE"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}✓ Found $FOUND_COUNT out of $AGENT_COUNT agents${NC}"
echo -e "${GREEN}✓ Configuration saved to: $CONFIG_FILE${NC}"
echo ""

if [ $FOUND_COUNT -gt 0 ]; then
    echo -e "${GREEN}Agent ARNs:${NC}"
    cat "$CONFIG_FILE" | jq -r '.agents | to_entries[] | "  • \(.key): \(.value.agent_arn)"'
    echo ""
    echo -e "${YELLOW}To use these ARNs in your applications:${NC}"
    echo "  - Python: import json; config = json.load(open('agent_arns.json'))"
    echo "  - Bash: cat agent_arns.json | jq -r '.agents.idp_extractor_agent.agent_arn'"
    echo ""
    echo -e "${YELLOW}To retrieve from SSM Parameter Store:${NC}"
    echo "  aws ssm get-parameter --name $SSM_PARAM_PREFIX/AGENT_NAME/arn --query Parameter.Value --output text"
else
    echo -e "${YELLOW}No agents found. Make sure to deploy the agents first using:${NC}"
    echo "  bash deploy_all_agents.sh"
fi

echo ""
