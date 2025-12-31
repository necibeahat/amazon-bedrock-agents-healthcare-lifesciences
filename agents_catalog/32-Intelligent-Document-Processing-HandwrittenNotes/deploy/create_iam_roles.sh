#!/bin/bash

# Script to create IAM roles required for IDP agents deployment
# Creates three roles with appropriate permissions for each agent

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Creating IAM Roles for IDP Agents${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}AWS Account ID: $AWS_ACCOUNT_ID${NC}"
echo ""

# Trust policy for AgentCore service
TRUST_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": [
          "bedrock-agentcore.amazonaws.com",
          "bedrock.amazonaws.com",
          "lambda.amazonaws.com"
        ]
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
)

# Function to create role
create_role() {
    local role_name=$1
    local description=$2
    
    echo -e "${YELLOW}Creating role: $role_name${NC}"
    
    if aws iam get-role --role-name "$role_name" &> /dev/null; then
        echo -e "${GREEN}✓ Role already exists: $role_name${NC}"
    else
        aws iam create-role \
            --role-name "$role_name" \
            --assume-role-policy-document "$TRUST_POLICY" \
            --description "$description"
        echo -e "${GREEN}✓ Created role: $role_name${NC}"
    fi
}

# Function to attach policy
attach_policy() {
    local role_name=$1
    local policy_arn=$2
    local policy_name=$3
    
    if aws iam list-attached-role-policies --role-name "$role_name" | grep -q "$policy_arn"; then
        echo -e "${GREEN}  ✓ Policy already attached: $policy_name${NC}"
    else
        aws iam attach-role-policy \
            --role-name "$role_name" \
            --policy-arn "$policy_arn"
        echo -e "${GREEN}  ✓ Attached policy: $policy_name${NC}"
    fi
}

# Function to create and attach inline policy
create_inline_policy() {
    local role_name=$1
    local policy_name=$2
    local policy_document=$3
    
    if aws iam get-role-policy --role-name "$role_name" --policy-name "$policy_name" &> /dev/null; then
        echo -e "${GREEN}  ✓ Inline policy already exists: $policy_name${NC}"
    else
        aws iam put-role-policy \
            --role-name "$role_name" \
            --policy-name "$policy_name" \
            --policy-document "$policy_document"
        echo -e "${GREEN}  ✓ Created inline policy: $policy_name${NC}"
    fi
}

# Create Extractor Agent Role
echo -e "${YELLOW}1. Creating Extractor Agent Role${NC}"
echo "--------------------------------------"
EXTRACTOR_ROLE="AgentCoreExecutionRole-IDP-Extractor"
create_role "$EXTRACTOR_ROLE" "Execution role for IDP Extractor Agent"

# Attach managed policies
attach_policy "$EXTRACTOR_ROLE" "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess" "CloudWatchLogsFullAccess"

# Create S3 policy
S3_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::idp-wwso-input-files",
        "arn:aws:s3:::idp-wwso-input-files/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": [
        "arn:aws:s3:::idp-wwso-output",
        "arn:aws:s3:::idp-wwso-output/*"
      ]
    }
  ]
}
EOF
)
create_inline_policy "$EXTRACTOR_ROLE" "S3AccessPolicy" "$S3_POLICY"

# Create Bedrock policy
BEDROCK_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    }
  ]
}
EOF
)
create_inline_policy "$EXTRACTOR_ROLE" "BedrockInvokePolicy" "$BEDROCK_POLICY"

# Create ECR policy
ECR_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchCheckLayerAvailability"
      ],
      "Resource": "*"
    }
  ]
}
EOF
)
create_inline_policy "$EXTRACTOR_ROLE" "ECRAccessPolicy" "$ECR_POLICY"

# Create BDA policy
BDA_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeDataAutomationAsync",
        "bedrock:GetDataAutomationStatus"
      ],
      "Resource": [
        "arn:aws:bedrock:*:${AWS_ACCOUNT_ID}:data-automation-project/*",
        "arn:aws:bedrock:*:${AWS_ACCOUNT_ID}:data-automation-profile/*",
        "arn:aws:bedrock:*:${AWS_ACCOUNT_ID}:data-automation-invocation/*"
      ]
    }
  ]
}
EOF
)
create_inline_policy "$EXTRACTOR_ROLE" "BDAAccessPolicy" "$BDA_POLICY"

echo ""

# Create Database Agent Role
echo -e "${YELLOW}2. Creating Database Agent Role${NC}"
echo "--------------------------------------"
DATABASE_ROLE="AgentCoreExecutionRole-IDP-Database"
create_role "$DATABASE_ROLE" "Execution role for IDP Database Agent"

# Attach managed policies
attach_policy "$DATABASE_ROLE" "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess" "CloudWatchLogsFullAccess"

# Create S3 read policy
S3_READ_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::idp-wwso-output",
        "arn:aws:s3:::idp-wwso-output/*"
      ]
    }
  ]
}
EOF
)
create_inline_policy "$DATABASE_ROLE" "S3ReadPolicy" "$S3_READ_POLICY"

# Create DynamoDB policy
DYNAMODB_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DescribeTable",
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:*:${AWS_ACCOUNT_ID}:table/IDP_Agent"
    }
  ]
}
EOF
)
create_inline_policy "$DATABASE_ROLE" "DynamoDBAccessPolicy" "$DYNAMODB_POLICY"

# Attach Bedrock policy
create_inline_policy "$DATABASE_ROLE" "BedrockInvokePolicy" "$BEDROCK_POLICY"

# Attach ECR policy
create_inline_policy "$DATABASE_ROLE" "ECRAccessPolicy" "$ECR_POLICY"

echo ""

# Create Quality Check Agent Role
echo -e "${YELLOW}3. Creating Quality Check Agent Role${NC}"
echo "--------------------------------------"
QUALITY_CHECK_ROLE="AgentCoreExecutionRole-IDP-QualityCheck"
create_role "$QUALITY_CHECK_ROLE" "Execution role for IDP Quality Check Agent"

# Attach managed policies
attach_policy "$QUALITY_CHECK_ROLE" "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess" "CloudWatchLogsFullAccess"

# Create DynamoDB full access policy
DYNAMODB_FULL_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:DescribeTable"
      ],
      "Resource": "arn:aws:dynamodb:*:${AWS_ACCOUNT_ID}:table/IDP_Agent"
    }
  ]
}
EOF
)
create_inline_policy "$QUALITY_CHECK_ROLE" "DynamoDBFullAccessPolicy" "$DYNAMODB_FULL_POLICY"

# Attach Bedrock policy
create_inline_policy "$QUALITY_CHECK_ROLE" "BedrockInvokePolicy" "$BEDROCK_POLICY"

# Attach ECR policy
create_inline_policy "$QUALITY_CHECK_ROLE" "ECRAccessPolicy" "$ECR_POLICY"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}IAM Roles Created Successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}Created Roles:${NC}"
echo "  1. $EXTRACTOR_ROLE"
echo "     ARN: arn:aws:iam::${AWS_ACCOUNT_ID}:role/$EXTRACTOR_ROLE"
echo ""
echo "  2. $DATABASE_ROLE"
echo "     ARN: arn:aws:iam::${AWS_ACCOUNT_ID}:role/$DATABASE_ROLE"
echo ""
echo "  3. $QUALITY_CHECK_ROLE"
echo "     ARN: arn:aws:iam::${AWS_ACCOUNT_ID}:role/$QUALITY_CHECK_ROLE"
echo ""
echo -e "${YELLOW}You can now run the agent deployment scripts.${NC}"
echo ""
