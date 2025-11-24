# IDP Agent Deployment Guide

Complete guide for deploying the three-agent IDP system to Amazon Bedrock AgentCore Runtime.

## Overview

This deployment process will create three independent agents:

1. **Extractor Agent** (`idp-extractor-agent`) - Processes PDFs from S3 using BDA MCP
2. **Database Agent** (`idp-database-agent`) - Imports extracted JSON data to DynamoDB  
3. **Quality Check Agent** (`idp-quality-check-agent`) - Enables querying and validation

## Architecture

```
PDF Files (S3) → Extractor Agent → JSON Files (S3) → Database Agent → DynamoDB → Quality Check Agent
```

## Prerequisites

Before deploying, ensure you have:

### 1. AWS Account & Configuration
- AWS CLI installed and configured
- Appropriate AWS credentials with permissions to:
  - Create IAM roles and policies
  - Create S3 buckets
  - Create DynamoDB tables
  - Deploy to Bedrock AgentCore
  - Create CloudWatch Log groups

```bash
aws configure
# Verify configuration
aws sts get-caller-identity
```

### 2. Python Environment
- Python 3.10 or higher
- pip installed
- Recommended: Use virtual environment

```bash
python --version
pip install bedrock-agentcore
```

### 3. Bedrock Model Access
Enable access to required models in Amazon Bedrock console:
- Anthropic Claude 3.7 Sonnet (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`)
- Anthropic Claude 3.5 Haiku (optional, for cost optimization)

Navigate to: AWS Console → Amazon Bedrock → Model access

### 4. BDA Project ARN
Update the `BDA_PROJECT_ARN` in `extractor_agent.py` with your Bedrock Data Automation project ARN.

```python
BDA_PROJECT_ARN = "arn:aws:bedrock:us-east-1:<account-id>:data-automation-project/<project-id>"
```

## Deployment Steps

### Step 1: Create IAM Roles

The agents require specific IAM roles with appropriate permissions. Run the IAM role creation script:

```bash
cd agents_catalog/32-Intelligent-Document-Processing-HandwrittenNotes/deploy
chmod +x create_iam_roles.sh
./create_iam_roles.sh
```

This creates three roles:
- `AgentCoreExecutionRole-IDP-Extractor`
- `AgentCoreExecutionRole-IDP-Database`
- `AgentCoreExecutionRole-IDP-QualityCheck`

**Manual Alternative:** If you prefer to create roles manually, ensure each role has:

#### Extractor Agent Role
- S3 read access to `idp-wwso-input-files`
- S3 write access to `idp-wwso-output`
- Bedrock model invocation permissions
- CloudWatch Logs permissions

#### Database Agent Role
- S3 read access to `idp-wwso-output`
- DynamoDB full access for `IDP_Agent` table
- Bedrock model invocation permissions
- CloudWatch Logs permissions

#### Quality Check Agent Role
- DynamoDB read/write access for `IDP_Agent` table
- Bedrock model invocation permissions
- CloudWatch Logs permissions

### Step 2: Deploy All Agents (Recommended)

Use the master deployment script to deploy all three agents sequentially:

```bash
chmod +x deploy_all_agents.sh
./deploy_all_agents.sh
```

This script will:
1. Deploy Extractor Agent
2. Deploy Database Agent
3. Deploy Quality Check Agent
4. Display next steps and usage instructions

**Note:** The script will pause between each agent deployment for you to review the output.

### Step 3: Deploy Individual Agents (Alternative)

If you prefer to deploy agents individually or troubleshoot specific agents:

#### Deploy Extractor Agent
```bash
chmod +x deploy_extractor_agent.sh
./deploy_extractor_agent.sh
```

#### Deploy Database Agent
```bash
chmod +x deploy_database_agent.sh
./deploy_database_agent.sh
```

#### Deploy Quality Check Agent
```bash
chmod +x deploy_quality_check_agent.sh
./deploy_quality_check_agent.sh
```

## Post-Deployment Verification

### 1. Verify Agent Deployments

Check that all agents are deployed:

```bash
aws bedrock-agent-runtime list-agents --region us-east-1
```

### 2. Verify S3 Buckets

```bash
aws s3 ls | grep idp-wwso
# Should show:
# idp-wwso-input-files
# idp-wwso-output
```

### 3. Upload Test Documents

```bash
aws s3 cp your-test-document.pdf s3://idp-wwso-input-files/input-pdfs/
```

### 4. Test Each Agent

#### Test Extractor Agent
```bash
agentcore invoke --name idp-extractor-agent '{"prompt": "Start extraction"}'
```

Expected output: JSON files in `s3://idp-wwso-output/extracted-data/`

#### Test Database Agent
```bash
agentcore invoke --name idp-database-agent '{"prompt": "Import data"}'
```

Expected output: Data imported to DynamoDB table `IDP_Agent`

#### Test Quality Check Agent
```bash
agentcore invoke --name idp-quality-check-agent '{"prompt": "List all documents"}'
```

Expected output: Query results from DynamoDB

## Usage Examples

### Complete Workflow

```bash
# 1. Upload PDFs
aws s3 cp document1.pdf s3://idp-wwso-input-files/input-pdfs/
aws s3 cp document2.pdf s3://idp-wwso-input-files/input-pdfs/

# 2. Extract data
agentcore invoke --name idp-extractor-agent '{"prompt": "Start extraction"}'

# 3. Import to database
agentcore invoke --name idp-database-agent '{"prompt": "Import data"}'

# 4. Query and validate
agentcore invoke --name idp-quality-check-agent '{"prompt": "List all patient names"}'
agentcore invoke --name idp-quality-check-agent '{"prompt": "Show fields with confidence < 0.8"}'
agentcore invoke --name idp-quality-check-agent '{"prompt": "validate patient_name for document abc-123"}'
agentcore invoke --name idp-quality-check-agent '{"prompt": "update phone to 555-9999 for document abc-123"}'
```

### Viewing Logs

```bash
# Extractor Agent logs
aws logs tail /aws/bedrock-agentcore/idp-extractor-agent --follow

# Database Agent logs
aws logs tail /aws/bedrock-agentcore/idp-database-agent --follow

# Quality Check Agent logs
aws logs tail /aws/bedrock-agentcore/idp-quality-check-agent --follow
```

### Viewing DynamoDB Data

```bash
# Scan all items
aws dynamodb scan --table-name IDP_Agent --max-items 10

# Get specific document
aws dynamodb get-item \
  --table-name IDP_Agent \
  --key '{"document_id": {"S": "your-uuid-here"}}'

# Query by document ID
aws dynamodb query \
  --table-name IDP_Agent \
  --key-condition-expression "document_id = :doc_id" \
  --expression-attribute-values '{":doc_id": {"S": "your-uuid-here"}}'
```

## Troubleshooting

### Common Issues

#### 1. "Role does not exist" error
**Solution:** Run `create_iam_roles.sh` to create the required IAM roles.

#### 2. "Access Denied" on S3
**Solution:** Verify the IAM role has correct S3 permissions and bucket names match.

#### 3. "Table does not exist" for DynamoDB
**Solution:** Run the Database Agent first - it will create the table automatically.

#### 4. BDA MCP connection errors
**Solution:** 
- Verify `BDA_PROJECT_ARN` is correctly set in `extractor_agent.py`
- Ensure the IAM role has Bedrock Data Automation permissions

#### 5. Container build fails
**Solution:**
- Check your AWS CodeBuild permissions
- Verify Python dependencies in `requirements.txt`
- Check CloudWatch Logs for detailed error messages

### Debug Mode

Enable verbose logging by setting environment variables:

```bash
export FASTMCP_LOG_LEVEL=DEBUG
export AWS_BEDROCK_AGENTCORE_LOG_LEVEL=DEBUG
```

## Updating Agents

To update an agent after making code changes:

```bash
cd agents_catalog/32-Intelligent-Document-Processing-HandwrittenNotes/agent

# Clean up existing configuration
rm -f .agentcore.yaml .bedrock_agentcore.yaml

# Reconfigure and redeploy
agentcore configure --entrypoint <agent_file>.py --requirements-file requirements.txt --execution-role-arn <role-arn> --name <agent-name>
agentcore launch
```

## Cleanup

To remove all deployed resources:

```bash
# Delete agents
agentcore delete --name idp-extractor-agent
agentcore delete --name idp-database-agent
agentcore delete --name idp-quality-check-agent

# Delete S3 buckets (remove objects first)
aws s3 rm s3://idp-wwso-input-files --recursive
aws s3 rb s3://idp-wwso-input-files
aws s3 rm s3://idp-wwso-output --recursive
aws s3 rb s3://idp-wwso-output

# Delete DynamoDB table
aws dynamodb delete-table --table-name IDP_Agent

# Delete IAM roles (remove policies first)
aws iam delete-role --role-name AgentCoreExecutionRole-IDP-Extractor
aws iam delete-role --role-name AgentCoreExecutionRole-IDP-Database
aws iam delete-role --role-name AgentCoreExecutionRole-IDP-QualityCheck
```

## Cost Optimization

- Use Claude Haiku for Quality Check Agent (lower cost for queries)
- Set DynamoDB table to on-demand billing mode
- Enable S3 lifecycle policies to archive old extracted data
- Use CloudWatch Logs retention policies to manage log storage

## Security Best Practices

1. **IAM Roles:** Use least-privilege access principles
2. **S3 Buckets:** Enable encryption at rest and versioning
3. **DynamoDB:** Enable point-in-time recovery
4. **Secrets:** Never hardcode credentials in code
5. **VPC:** Consider deploying in private subnets for production

## Support

For issues or questions:
- Review CloudWatch Logs for error details
- Check the main [README.md](../README.md) for architecture details
- See [AGENTS_GUIDE.md](../AGENTS_GUIDE.md) for detailed agent documentation
- Refer to [AWS Bedrock AgentCore documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)

## Next Steps

After successful deployment:
1. Integrate with your frontend application (see `app_orchestrator.py`)
2. Set up CI/CD pipeline for automated deployments
3. Configure monitoring and alerting
4. Implement batch processing for high-volume scenarios
5. Add custom validation rules in Quality Check Agent
