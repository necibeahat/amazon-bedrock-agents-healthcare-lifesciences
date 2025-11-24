#!/bin/bash

# Deployment script for IDP Database Agent to Amazon Bedrock AgentCore
# This agent imports extracted JSON data from S3 into DynamoDB

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
AGENT_NAME="idp_database_agent"
AGENT_FILE="database_agent.py"
REQUIREMENTS_FILE="requirements.txt"
AGENT_DIR="../agent"
DYNAMODB_TABLE_NAME="IDP_Agent"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deploying IDP Database Agent${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if we're in the correct directory
if [ ! -d "$AGENT_DIR" ]; then
    echo -e "${RED}Error: Agent directory not found. Please run this script from the deploy directory.${NC}"
    exit 1
fi

# Check if agent file exists
if [ ! -f "$AGENT_DIR/$AGENT_FILE" ]; then
    echo -e "${RED}Error: $AGENT_FILE not found in $AGENT_DIR${NC}"
    exit 1
fi

# Check if requirements.txt exists
if [ ! -f "$AGENT_DIR/$REQUIREMENTS_FILE" ]; then
    echo -e "${RED}Error: $REQUIREMENTS_FILE not found in $AGENT_DIR${NC}"
    exit 1
fi

# Check AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    exit 1
fi

# Check if agentcore is installed
if ! command -v agentcore &> /dev/null; then
    echo -e "${YELLOW}Warning: agentcore CLI not found. Installing...${NC}"
    pip install bedrock-agentcore
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

# Check if S3 output bucket exists
echo -e "${YELLOW}Checking S3 output bucket...${NC}"
if aws s3 ls s3://idp-wwso-output &> /dev/null; then
    echo -e "${GREEN}✓ Output bucket exists: s3://idp-wwso-output${NC}"
else
    echo -e "${YELLOW}Creating output bucket: s3://idp-wwso-output${NC}"
    aws s3 mb s3://idp-wwso-output
fi
echo ""

# Change to agent directory
cd "$AGENT_DIR"

# Clean up any existing configuration
if [ -f ".agentcore.yaml" ]; then
    echo -e "${YELLOW}Removing existing .agentcore.yaml${NC}"
    rm -f .agentcore.yaml
fi

if [ -f ".bedrock_agentcore.yaml" ]; then
    echo -e "${YELLOW}Removing existing .bedrock_agentcore.yaml${NC}"
    rm -f .bedrock_agentcore.yaml
fi

echo -e "${GREEN}Step 1: Configuring AgentCore${NC}"
echo "--------------------------------------"

# Check if IAM role exists, if not prompt user
IAM_ROLE_NAME="AgentCoreExecutionRole-IDP-Database"
IAM_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${IAM_ROLE_NAME}"

if aws iam get-role --role-name "$IAM_ROLE_NAME" &> /dev/null; then
    echo -e "${GREEN}✓ Using existing IAM role: $IAM_ROLE_NAME${NC}"
else
    echo -e "${YELLOW}IAM role not found. You need to create an execution role with:${NC}"
    echo "  - S3 read access to idp-wwso-output bucket"
    echo "  - DynamoDB full access for $DYNAMODB_TABLE_NAME table"
    echo "  - Bedrock model invocation permissions"
    echo "  - CloudWatch Logs permissions"
    echo ""
    echo -e "${YELLOW}Please create the role and press Enter to continue, or Ctrl+C to exit${NC}"
    read -r
fi

# Configure AgentCore
echo -e "${YELLOW}Configuring AgentCore for $AGENT_NAME...${NC}"
agentcore configure \
    --entrypoint "$AGENT_FILE" \
    --requirements-file "$REQUIREMENTS_FILE" \
    --execution-role "$IAM_ROLE_ARN" \
    --name "$AGENT_NAME"

echo -e "${GREEN}✓ Configuration complete${NC}"
echo ""

echo -e "${GREEN}Step 2: Launching Agent to AgentCore Runtime${NC}"
echo "--------------------------------------"
echo -e "${YELLOW}This will build a container and deploy to AWS...${NC}"
echo ""

# Launch the agent
agentcore launch

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}Agent Name: $AGENT_NAME${NC}"
echo -e "${GREEN}Region: $AWS_REGION${NC}"
echo -e "${GREEN}DynamoDB Table: $DYNAMODB_TABLE_NAME${NC}"
echo ""
echo -e "${YELLOW}To test the agent:${NC}"
echo "  agentcore invoke '{\"prompt\": \"Import data\"}'"
echo ""
echo -e "${YELLOW}To view DynamoDB table:${NC}"
echo "  aws dynamodb scan --table-name $DYNAMODB_TABLE_NAME --max-items 5"
echo ""
echo -e "${YELLOW}To view logs:${NC}"
echo "  aws logs tail /aws/bedrock-agentcore/$AGENT_NAME --follow"
echo ""
