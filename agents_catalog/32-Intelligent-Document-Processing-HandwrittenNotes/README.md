# Intelligent Document Processing (IDP) Agent

## Table of Contents
- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [Solution](#solution)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [Deployment](#deployment)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Cost Optimization](#cost-optimization)
- [Resources](#resources)

## Overview

A three-agent system powered by Amazon Bedrock AgentCore, Strands SDK, and Bedrock Data Automation (BDA) MCP for processing documents of any type including forms, invoices, medical records, contracts, and handwritten notes. The system extracts structured data, stores it in DynamoDB, and enables natural language queries for validation and updates.

### Three-Agent Architecture

1. **Extractor Agent** (`agent/extractor_agent.py`) - Processes PDFs using BDA MCP and saves JSON to S3
2. **Database Agent** (`agent/database_agent.py`) - Imports extracted data into DynamoDB
3. **Quality Check Agent** (`agent/quality_check_agent.py`) - Enables querying, validation, and field updates

**Why Three Agents?**
- **Separation of Concerns**: Each agent has focused responsibility
- **Flexible Workflow**: Run independently or in sequence
- **Better Data Management**: Structured storage with query capabilities
- **Independent Scaling**: Different resource requirements per agent

### Demo

📹 [Watch Demo Video](demo/IDP_SampleDoc_Demo.mov)

*The demo shows the IDP agent extracting structured data from documents and enabling conversational queries for validation and updates.*

## Problem Statement

Intelligent Document Processing (IDP) extracts structured data from unstructured documents. Unstructured data comprises 80% of enterprise data but remains largely untapped due to complexity.

Organizations processing documents face challenges:
- **Time-consuming**: Manual review takes 10-15 minutes per document
- **High Error Rates**: Manual processing has up to 4% error rate  
- **Costly**: Current OCR solutions achieve only 70% accuracy at $5-15 per document
- **Inefficient**: No ability to ask follow-up questions without re-reading documents

## Solution

A BDA-powered IDP system that:
- ✅ Extracts structured data from any document type with confidence scores
- ✅ Stores data in DynamoDB for querying and validation
- ✅ Enables natural language queries without reprocessing
- ✅ Supports validation and updates through conversational interface
- ✅ Handles multimodal content (handwriting, printed text, checkboxes, tables, signatures)

### Key Features
- **Universal Document Support**: Process any document type (forms, invoices, contracts, medical records, etc.)
- **Multimodal Processing**: Handwritten and printed text, checkboxes, tables, and signatures
- **Confidence Scoring**: Per-field confidence scores for quality assurance
- **Structured Output**: JSON format with schema validation
- **Conversational Interface**: Ask follow-up questions without reprocessing
- **Validation & Updates**: Mark fields as validated or update incorrect extractions
- **Batch Processing**: Handle multiple documents simultaneously

## Architecture

### High-Level Architecture

```
PDF Files (S3) → Extractor Agent → JSON Files (S3) → Database Agent → DynamoDB → Quality Check Agent
                      ↓                                      ↓                          ↓
                 BDA MCP Server                      Table Creation           Query/Validate/Update
```

![Architecture Diagram](architecture/IDP_Agent_Architecture.png)

### Agent Workflows

**Extractor Agent:**
```
User: "Start extraction"
  ↓
List PDFs in S3 input bucket
  ↓
For each PDF:
  - Download from S3
  - Process with BDA MCP
  - Extract structured data
  - Save JSON to S3 output bucket
  ↓
Return summary report
```

**Database Agent:**
```
User: "Import data"
  ↓
Create DynamoDB table (if not exists)
  ↓
List JSON files in S3 output bucket
  ↓
For each JSON:
  - Download and parse
  - Add metadata (timestamp, validation status)
  - Write to DynamoDB
  ↓
Return import summary
```

**Quality Check Agent:**
```
User: "What is the patient name?" or
      "validate phone for document abc-123" or
      "update address to new value for document xyz-456"
  ↓
Query DynamoDB for document data
  ↓
Process request:
  - Answer questions
  - Validate fields (mark as validated)
  - Update field values
  ↓
Return results with confirmation
```

## Technology Stack

### Amazon Bedrock AgentCore
Serverless runtime for deploying and scaling AI agents:
- Automatic scaling and load balancing
- Built-in observability and monitoring
- IAM-based security and access control

### Strands Agent SDK
Multi-agent orchestration framework:
- Agent loop with reasoning and tool use
- Conversation state management
- Flexible tool integration (Python, MCP, community tools)

### Bedrock Data Automation (BDA) MCP
Multimodal document processing via Model Context Protocol:
- PDF to structured data conversion
- Handwriting recognition
- Visual element extraction (checkboxes, tables, signatures)

### AWS Services
- **Amazon S3**: Document storage (input PDFs, extracted JSON)
- **Amazon DynamoDB**: Structured data storage and querying
- **AWS IAM**: Role-based access control
- **Amazon CloudWatch**: Logging and monitoring

## Prerequisites

Before deploying, ensure you have:

### 1. AWS Account & Configuration
```bash
# AWS CLI installed and configured
aws configure

# Verify configuration
aws sts get-caller-identity
```

Required permissions:
- Create IAM roles and policies
- Create S3 buckets
- Create DynamoDB tables
- Deploy to Bedrock AgentCore
- Create CloudWatch Log groups

### 2. Python Environment
- Python 3.11+
- `uv` package manager: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- bedrock-agentcore CLI: `pip install bedrock-agentcore`

### 3. Bedrock Model Access
Enable access in Amazon Bedrock console:
- Anthropic Claude 3.7 Sonnet (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`)
- Anthropic Claude 3.5 Haiku (optional, for cost optimization)

Navigate to: **AWS Console → Amazon Bedrock → Model access**

### 4. BDA Project ARN
Create a Bedrock Data Automation project and update the ARN in `extractor_agent.py`:

```python
BDA_PROJECT_ARN = "arn:aws:bedrock:us-east-1:<account-id>:data-automation-project/<project-id>"
```

### 5. Configuration
Edit configuration constants in each agent file as needed:

```python
# Extractor Agent (extractor_agent.py)
INPUT_BUCKET = "idp-wwso-input-files"
OUTPUT_BUCKET = "idp-wwso-output"

# Database & Quality Check Agents
DYNAMODB_TABLE_NAME = "IDP_Agent"
```

## Deployment

### Quick Start

For detailed deployment instructions, see [DEPLOYMENT_README.md](deploy/DEPLOYMENT_README.md)

### Step 1: Create S3 Buckets

```bash
# Create input bucket for PDFs
aws s3 mb s3://idp-wwso-input-files

# Create output bucket for extracted JSON
aws s3 mb s3://idp-wwso-output
```

### Step 2: Create IAM Roles

```bash
cd agents_catalog/32-Intelligent-Document-Processing-HandwrittenNotes/deploy
chmod +x create_iam_roles.sh
./create_iam_roles.sh
```

This creates three roles with appropriate permissions:
- `AgentCoreExecutionRole-IDP-Extractor`
- `AgentCoreExecutionRole-IDP-Database`
- `AgentCoreExecutionRole-IDP-QualityCheck`

### Step 3: Deploy All Agents

```bash
chmod +x deploy_all_agents.sh
./deploy_all_agents.sh
```

**Or deploy individually:**

```bash
# Deploy Extractor Agent
./deploy_extractor_agent.sh

# Deploy Database Agent
./deploy_database_agent.sh

# Deploy Quality Check Agent
./deploy_quality_check_agent.sh
```

### Step 4: Verify Deployment

```bash
# List deployed agents
aws bedrock-agent-runtime list-agents --region us-east-1

# Check S3 buckets
aws s3 ls | grep idp-wwso
```

## Usage

### Running the Streamlit UI

**Unified Orchestrator (Recommended):**
```bash
streamlit run app_idp_frontend.py
```

The orchestrator provides:
- 🔄 **Sequential Processing** - Run all three agents automatically
- Individual agent tabs with independent triggers
- Interactive Quality Check chat interface

### 3-Step User Workflow

The Streamlit UI simplifies document processing into three intuitive steps:

#### Step 1: Extract & Persist to Database

Upload your documents to S3 and click **"Start Extraction"** in the Extractor Agent tab.

**What happens:**
- Documents are processed using Bedrock Data Automation (BDA) with advanced AI models
- Structured data is extracted with **confidence scores** for each field (0.0 to 1.0)
- Extracted data is automatically saved to **DynamoDB** for persistent storage
- Each document receives a unique identifier for tracking

**Confidence Scores:**
- **0.9-1.0**: High confidence - extraction is very reliable
- **0.7-0.89**: Good confidence - likely correct but review recommended
- **0.5-0.69**: Medium confidence - review and validation needed
- **Below 0.5**: Low confidence - manual verification required

**Example Output:**
```
✅ Processed 3 documents
Document ID: abc-123-def
  - patient_name: "John Doe" (confidence: 0.95)
  - date_of_birth: "1980-05-15" (confidence: 0.88)
  - phone: "555-1234" (confidence: 0.72)
  - Status: Imported to DynamoDB
```

#### Step 2: Review Extraction Quality

Navigate to the Database Agent tab to view extraction results and quality metrics.

**What you can do:**
- **Review confidence scores** for all extracted fields across all documents
- **Validate correct extractions**: Mark fields as validated when you confirm they're accurate
- **Update incorrect extractions**: Correct any errors directly through the interface
- **Filter by confidence**: Identify fields that need review (e.g., confidence < 0.8)

**Validation & Updates:**
```
# Validate a correct extraction
"validate patient_name for document abc-123-def"
Response: ✅ Successfully validated patient_name field

# Update an incorrect extraction
"update phone to 555-9876 for document abc-123-def"
Response: ✅ Successfully updated phone to 555-9876 (validation status reset to false)
```

**Note:** When you update a field, its validation status is automatically reset to `false`, prompting a re-review of the corrected data.

#### Step 3: Query with Natural Language

Use the Quality Check Agent tab to ask questions about your extracted data using natural language.

**Multi-Document Queries:**

The system searches across **all extracted documents** and returns comprehensive results including:
- Field values from all matching documents
- Validation status (validated vs. unvalidated)
- Confidence scores for each field
- Document identifiers for reference

**Example Query:**
```
Question: "What is the patient name?"

Answer:
📄 Document abc-123-def:
   - patient_name: "John Doe"
   - Validation Status: ✅ Validated
   - Confidence Score: 0.95

📄 Document xyz-789-ghi:
   - patient_name: "Jane Smith"  
   - Validation Status: ⚠️ Not Validated
   - Confidence Score: 0.73

📄 Document mno-456-pqr:
   - patient_name: "Robert Johnson"
   - Validation Status: ✅ Validated
   - Confidence Score: 0.91
```

**Advanced Queries:**
```
# Find low-confidence extractions
"Show all fields with confidence score less than 0.8"

# Find unvalidated data
"List all unvalidated fields across all documents"

# Specific document queries
"What information do we have for document abc-123-def?"

# Cross-document analytics
"How many documents have been processed?"
"Which documents have patient_age greater than 50?"
```

**Benefits of This Workflow:**
- ✅ **Automated extraction** reduces manual data entry by 90%
- ✅ **Confidence scoring** helps prioritize review efforts
- ✅ **Validation tracking** ensures data quality and compliance
- ✅ **Natural language queries** eliminate the need for database expertise
- ✅ **Multi-document search** provides instant insights across your entire document collection

### Command-Line Usage

#### 1. Upload Documents
```bash
aws s3 cp your-document.pdf s3://idp-wwso-input-files/input-pdfs/
```

#### 2. Extract Data
```bash
# Via Streamlit: Navigate to Extractor Agent tab, click "Start Extraction"
# Or via CLI:
agentcore invoke --name idp-extractor-agent '{"prompt": "Start extraction"}'
```

**Output:**
- Processes all PDFs in `s3://idp-wwso-input-files/input-pdfs/`
- Saves JSON to `s3://idp-wwso-output/extracted-data/`
- Each document gets a unique UUID

#### 3. Import to Database
```bash
# Via Streamlit: Navigate to Database Agent tab, click "Import Data"
# Or via CLI:
agentcore invoke --name idp-database-agent '{"prompt": "Import data"}'
```

**Output:**
- Creates DynamoDB table `IDP_Agent` if needed
- Imports all JSON files
- Adds `validated: false` to all fields

#### 4. Query & Validate
```bash
# Via Streamlit: Use Quality Check Agent chat interface
# Or via CLI:
agentcore invoke --name idp-quality-check-agent '{"prompt": "What is the patient name?"}'
agentcore invoke --name idp-quality-check-agent '{"prompt": "validate phone for document abc-123"}'
agentcore invoke --name idp-quality-check-agent '{"prompt": "update phone to 555-9999 for document abc-123"}'
```

### Example Queries

**Ask questions:**
```
"What is the patient name?"
"List all unvalidated fields"
"Show fields with confidence score less than 0.8"
"How many documents have been processed?"
```

**Validate correct extraction:**
```
"validate patient_name for document abc-123-def"
"validate all fields for document abc-123-def"
```

**Update incorrect extraction:**
```
"update phone to 555-9999 for document abc-123-def"
"update address to 123 Main St for document abc-123-def"
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

# Query specific document
aws dynamodb query \
  --table-name IDP_Agent \
  --key-condition-expression "document_id = :doc_id" \
  --expression-attribute-values '{":doc_id": {"S": "your-uuid-here"}}'
```

### Complete Workflow Example

Here's a complete end-to-end example:

```bash
# 1. Upload PDFs
aws s3 cp form1.pdf s3://idp-wwso-input-files/input-pdfs/
aws s3 cp form2.pdf s3://idp-wwso-input-files/input-pdfs/

# 2. Extract data (via Streamlit or CLI)
# In Streamlit: Click "Start Extraction" in Extractor Agent tab
# Result: ✅ Processed 2 files

# 3. Import to database (via Streamlit or CLI)
# In Streamlit: Click "Import Data" in Database Agent tab  
# Result: ✅ Imported 2 documents

# 4. Query data
# In Quality Check chat: "List all patient names"
# Response: Document abc-123: John Doe
#           Document def-456: Jane Smith

# 5. Validate fields
# In Quality Check chat: "validate patient_name for document abc-123"
# Response: ✅ Successfully validated patient_name

# 6. Update incorrect data
# In Quality Check chat: "update phone to 555-8888 for document abc-123"
# Response: ✅ Successfully updated phone to 555-8888
```

### Data Flow

```
PDF Files (S3: idp-wwso-input-files/input-pdfs/)
    ↓
Extractor Agent (BDA MCP processing)
    ↓
JSON Files (S3: idp-wwso-output/extracted-data/)
    ↓
Database Agent (DynamoDB import)
    ↓
DynamoDB Table (IDP_Agent)
    ↓
Quality Check Agent (Query/Validate/Update)
```

## Project Structure

```
agents_catalog/32-Intelligent-Document-Processing-HandwrittenNotes/
├── agent/
│   ├── extractor_agent.py           # Agent 1: PDF → JSON extraction
│   ├── database_agent.py             # Agent 2: JSON → DynamoDB import
│   ├── quality_check_agent.py        # Agent 3: Query & validation
│   ├── requirements.txt              # Python dependencies
│   └── .bedrock_agentcore.yaml      # AgentCore configuration
├── deploy/
│   ├── DEPLOYMENT_README.md          # Detailed deployment guide
│   ├── create_iam_roles.sh          # IAM role creation script
│   ├── deploy_all_agents.sh         # Deploy all agents
│   ├── deploy_extractor_agent.sh    # Deploy extractor individually
│   ├── deploy_database_agent.sh     # Deploy database individually
│   └── deploy_quality_check_agent.sh # Deploy quality check individually
├── app_idp_frontend.py              # Streamlit UI with orchestration
├── data/                             # Sample input documents
├── demo/                             # Demo videos and GIFs
├── architecture/                     # Architecture diagrams
├── test/                            # Test files and documentation
└── README.md                        # This file
```

## Testing

### Test Individual Agents

```bash
# Test Extractor Agent
cd test
python test_extractor_agent.py

# Test Database Agent
python test_database_agent.py

# Test Quality Check Agent
python test_quality_check_agent.py
```

### End-to-End Test

```bash
# Upload test document
aws s3 cp data/sample-form.pdf s3://idp-wwso-input-files/input-pdfs/

# Run sequential workflow
streamlit run app_idp_frontend.py
# Use "Sequential Processing" tab to run all agents

# Verify results
aws dynamodb scan --table-name IDP_Agent
```

### Performance Metrics

- **Extraction**: 20-30 seconds per document (includes S3 download + BDA processing)
- **Database Import**: 1-2 seconds per document
- **Query Response**: <2 seconds (reads from DynamoDB)
- **Throughput**: Supports 200-300 documents/day
- **Accuracy**: Confidence scores provided per field

## Cost Optimization

1. **File Caching**: Downloads from S3 are cached in `/tmp/` for container reuse
2. **Model Selection**: Use Claude Haiku for Quality Check Agent (lower cost)
3. **DynamoDB**: Use on-demand billing mode for variable workloads
4. **S3 Lifecycle**: Archive old extracted data to Glacier
5. **CloudWatch Logs**: Set retention policies (7-30 days)

### Estimated Costs (per 1,000 documents)

- **Bedrock AgentCore**: $5-10 (compute time)
- **Bedrock Models**: $15-30 (API calls)
- **BDA Processing**: $20-40 (document analysis)
- **S3 Storage**: $1-2
- **DynamoDB**: $2-5 (on-demand)
- **Total**: ~$45-90 per 1,000 documents

## Troubleshooting

### Common Issues

**"Role does not exist" error:**
```bash
# Solution: Run IAM role creation script
cd deploy
./create_iam_roles.sh
```

**"Access Denied" on S3:**
- Verify IAM role has S3 permissions
- Check bucket names match configuration
- Ensure buckets exist

**"Table does not exist" for DynamoDB:**
- Run Database Agent first to create table
- Verify table name matches configuration

**BDA MCP connection errors:**
- Verify `BDA_PROJECT_ARN` in `extractor_agent.py`
- Ensure IAM role has Bedrock Data Automation permissions

**Container build fails:**
- Check AWS CodeBuild permissions
- Verify Python dependencies in `requirements.txt`
- Check CloudWatch Logs for detailed errors

### Debug Mode

Enable verbose logging:
```bash
export FASTMCP_LOG_LEVEL=DEBUG
export AWS_BEDROCK_AGENTCORE_LOG_LEVEL=DEBUG
```

## Security Best Practices

1. **IAM Roles**: Use least-privilege access principles
2. **S3 Buckets**: Enable encryption at rest and versioning
3. **DynamoDB**: Enable point-in-time recovery
4. **Secrets**: Never hardcode credentials
5. **VPC**: Deploy in private subnets for production
6. **Data Privacy**: Ensure HIPAA compliance if processing PHI

## Cleanup

To remove all deployed resources:

```bash
# Delete agents
agentcore delete --name idp-extractor-agent
agentcore delete --name idp-database-agent
agentcore delete --name idp-quality-check-agent

# Delete S3 buckets
aws s3 rm s3://idp-wwso-input-files --recursive
aws s3 rb s3://idp-wwso-input-files
aws s3 rm s3://idp-wwso-output --recursive
aws s3 rb s3://idp-wwso-output

# Delete DynamoDB table
aws dynamodb delete-table --table-name IDP_Agent

# Delete IAM roles
aws iam delete-role --role-name AgentCoreExecutionRole-IDP-Extractor
aws iam delete-role --role-name AgentCoreExecutionRole-IDP-Database
aws iam delete-role --role-name AgentCoreExecutionRole-IDP-QualityCheck
```

## Resources

- [Deployment Guide](deploy/DEPLOYMENT_README.md) - Complete deployment instructions
- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Strands Agents Framework](https://github.com/awslabs/strands-agents)
- [Bedrock Data Automation](https://aws.amazon.com/bedrock/data-automation/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)

## Next Steps

**Already Implemented:**
- ✅ **Human-in-the-loop review workflow**: Users can validate and update extractions through the Quality Check Agent
- ✅ **Export data for downstream analysis**: Extracted data can be downloaded from DynamoDB for integration with CRM, EHR, and other systems

**Future Enhancements:**
- [ ] Add support for additional document formats (beyond PDF)
- [ ] Implement advanced batch processing for high-volume scenarios (1000+ documents/day)
- [ ] Add comprehensive audit logging and compliance tracking
- [ ] Implement custom validation rules engine
- [ ] Set up CI/CD pipeline for automated deployments
- [ ] Configure advanced monitoring and alerting dashboards
- [ ] Add role-based access control (RBAC) for multi-user environments
- [ ] Implement document versioning and change tracking

## Contributing

See the main repository [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines on contributing to this project.

## License

This project is licensed under the MIT-0 License. See [LICENSE](../../LICENSE) for details.

## Legal Notes

**Important**: This solution is for demonstrative purposes only. It is not for clinical use and is not a substitute for professional medical advice, diagnosis, or treatment. Before using AWS in connection with protected health information, customers must enter an AWS Business Associate Addendum (BAA) and follow its configuration requirements.
