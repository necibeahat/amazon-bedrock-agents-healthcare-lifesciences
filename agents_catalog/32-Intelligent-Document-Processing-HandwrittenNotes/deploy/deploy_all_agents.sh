#!/bin/bash

# Master deployment script for all three IDP agents to Amazon Bedrock AgentCore
# Deploys Extractor, Database, and Quality Check agents in sequence

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}IDP Multi-Agent Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}This script will deploy all three IDP agents:${NC}"
echo "  1. Extractor Agent - Processes PDFs using BDA MCP"
echo "  2. Database Agent - Imports data to DynamoDB"
echo "  3. Quality Check Agent - Query and validation"
echo ""

# Check if we're in the deploy directory
if [ ! -f "deploy_extractor_agent.sh" ]; then
    echo -e "${RED}Error: Please run this script from the deploy directory${NC}"
    exit 1
fi

# Prompt for confirmation
echo -e "${YELLOW}Do you want to proceed with deploying all agents? (y/n)${NC}"
read -r response
if [[ ! "$response" =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Step 1: Deploying Extractor Agent${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if bash deploy_extractor_agent.sh; then
    echo -e "${GREEN}✓ Extractor Agent deployed successfully${NC}"
else
    echo -e "${RED}✗ Extractor Agent deployment failed${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Press Enter to continue with Database Agent deployment...${NC}"
read -r

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Step 2: Deploying Database Agent${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if bash deploy_database_agent.sh; then
    echo -e "${GREEN}✓ Database Agent deployed successfully${NC}"
else
    echo -e "${RED}✗ Database Agent deployment failed${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Press Enter to continue with Quality Check Agent deployment...${NC}"
read -r

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Step 3: Deploying Quality Check Agent${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if bash deploy_quality_check_agent.sh; then
    echo -e "${GREEN}✓ Quality Check Agent deployed successfully${NC}"
else
    echo -e "${RED}✗ Quality Check Agent deployment failed${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}All Agents Deployed Successfully!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get AWS region
AWS_REGION=$(aws configure get region)
if [ -z "$AWS_REGION" ]; then
    AWS_REGION="us-east-1"
fi

echo -e "${GREEN}Deployed Agents:${NC}"
echo "  1. idp_extractor_agent"
echo "  2. idp_database_agent"
echo "  3. idp_quality_check_agent"
echo ""
echo -e "${GREEN}Region:${NC} $AWS_REGION"
echo ""

# Load and persist Agent ARNs
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Loading Agent ARNs${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if bash load_agent_arns.sh; then
    echo -e "${GREEN}✓ Agent ARNs loaded and persisted successfully${NC}"
else
    echo -e "${YELLOW}! Warning: Could not load Agent ARNs automatically${NC}"
    echo -e "${YELLOW}  You can manually run: bash load_agent_arns.sh${NC}"
fi
echo ""

echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo -e "${GREEN}1. Upload PDF files to S3:${NC}"
echo "   aws s3 cp your-document.pdf s3://idp-wwso-input-files/input-pdfs/"
echo ""
echo -e "${GREEN}2. Run the extraction:${NC}"
echo "   agentcore invoke --name idp_extractor_agent '{\"prompt\": \"Start extraction\"}'"
echo ""
echo -e "${GREEN}3. Import to database:${NC}"
echo "   agentcore invoke --name idp_database_agent '{\"prompt\": \"Import data\"}'"
echo ""
echo -e "${GREEN}4. Query and validate:${NC}"
echo "   agentcore invoke --name idp_quality_check_agent '{\"prompt\": \"List all patient names\"}'"
echo ""
echo -e "${YELLOW}For more information, see the DEPLOYMENT_README.md file${NC}"
echo ""
