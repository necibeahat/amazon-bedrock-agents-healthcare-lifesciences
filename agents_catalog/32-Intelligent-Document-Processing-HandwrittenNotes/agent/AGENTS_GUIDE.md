# Intelligent Document Processing - Three-Agent System

This project splits the IDP workflow into three specialized agents that work independently:

## Architecture Overview

```
┌─────────────────┐      ┌──────────────────┐      ┌────────────────────┐
│  1. Extractor   │      │  2. Database     │      │  3. Quality Check  │
│     Agent       │─────▶│     Agent        │─────▶│      Agent         │
│                 │      │                  │      │                    │
│  S3 Input       │      │  S3 → DynamoDB   │      │  Query & Validate  │
│  BDA MCP        │      │  Structured      │      │  Update Fields     │
│  JSON Output    │      │  Storage         │      │  Answer Questions  │
└─────────────────┘      └──────────────────┘      └────────────────────┘
```

## Agent Details

### 1. Extractor Agent (`extractor_agent.py`)

**Purpose:** Processes PDF documents using BDA MCP and saves structured JSON to S3

**Input:**
- PDF files from: `s3://idp-wwso-input-files/input-pdfs/`

**Output:**
- JSON files to: `s3://idp-wwso-output/extracted-data/{document_id}.json`

**Features:**
- Batch processing of multiple PDFs
- Uses AWS Bedrock Data Automation MCP for extraction
- Generates unique document IDs (UUID)
- Extracts fields with confidence scores
- Adds `validated: false` to all fields by default

**Output JSON Structure:**
```json
{
  "document_id": "uuid-here",
  "source_file": "s3://bucket/path/to/file.pdf",
  "extraction_timestamp": "2025-01-24T20:00:00.000Z",
  "extracted_data": {
    "extracted_fields": {
      "patient_name": {
        "value": "John Doe",
        "confidence": 0.95,
        "validated": false
      },
      "phone_number": {
        "value": "555-1234",
        "confidence": 0.87,
        "validated": false
      }
    }
  }
}
```

**Usage:**
- Deploy as a Bedrock AgentCore agent
- Trigger with any prompt (e.g., "Start extraction")
- Processes all PDFs in input bucket automatically

---

### 2. Database Agent (`database_agent.py`)

**Purpose:** Loads extracted JSON from S3 and stores in DynamoDB

**Input:**
- JSON files from: `s3://idp-wwso-output/extracted-data/`

**Output:**
- DynamoDB Table: `IDP_Agent`
- Primary Key: `document_id` (String)

**Features:**
- Creates DynamoDB table if it doesn't exist
- Batch processes all JSON files
- Ensures `validated` field exists for all fields
- Adds database import timestamp
- On-demand billing mode (pay per request)

**DynamoDB Schema:**
```json
{
  "document_id": "uuid-here",
  "source_file": "s3://bucket/path/to/file.pdf",
  "extraction_timestamp": "2025-01-24T20:00:00.000Z",
  "database_import_timestamp": "2025-01-24T20:05:00.000Z",
  "last_updated": "2025-01-24T20:10:00.000Z",
  "extracted_fields": {
    "field_name": {
      "value": "extracted_value",
      "confidence": 0.95,
      "validated": false
    }
  },
  "metadata": {}
}
```

**Usage:**
- Deploy as a Bedrock AgentCore agent
- Trigger with any prompt (e.g., "Import data")
- Processes all JSON files in S3 output bucket

---

### 3. Quality Check Agent (`quality_check_agent.py`)

**Purpose:** Query extracted data, validate fields, and update incorrect extractions

**Input:**
- DynamoDB Table: `IDP_Agent`

**Features:**

#### 1. Answer Questions
Ask natural language questions about the extracted data:
- "What is the patient's name?"
- "List all documents with unvalidated fields"
- "Show me fields with confidence below 0.9"
- "How many documents have been processed?"

#### 2. Validate Fields
Confirm that an extraction is correct without changing the value:
```
validate phone for document abc-123-def
```

This sets `validated: true` for the field.

#### 3. Update Fields
Correct an incorrect extraction:
```
update phone to 555-9876 for document abc-123-def
```

This:
- Updates the field value
- Sets `validated: true`
- Sets `confidence: 1.0`
- Updates `last_updated` timestamp

**Usage:**
- Deploy as a Bedrock AgentCore agent
- Ask questions in natural language
- Use specific commands for validation/updates

---

## Deployment Guide

### Prerequisites

1. AWS Account with appropriate permissions:
   - S3: Read/Write access
   - DynamoDB: Create/Read/Write tables
   - Bedrock: Access to Claude models
   - AgentCore: Deploy and invoke agents

2. S3 Buckets:
   ```bash
   # Create input bucket
   aws s3 mb s3://idp-wwso-input-files
   
   # Create output bucket
   aws s3 mb s3://idp-wwso-output
   
   # Create input folder
   aws s3api put-object --bucket idp-wwso-input-files --key input-pdfs/
   ```

3. Upload sample PDFs:
   ```bash
   aws s3 cp your-document.pdf s3://idp-wwso-input-files/input-pdfs/
   ```

### Deploy Agents

Each agent can be deployed independently using Bedrock AgentCore:

```bash
# Navigate to project directory
cd agents_catalog/32-Intelligent-Document-Processing-HandwrittenNotes

# Deploy Extractor Agent
uv run agent/extractor_agent.py

# Deploy Database Agent (in separate terminal)
uv run agent/database_agent.py

# Deploy Quality Check Agent (in separate terminal)
uv run agent/quality_check_agent.py
```

Or deploy through the Bedrock AgentCore Console/API.

---

## Workflow

### Complete Processing Pipeline

1. **Upload PDFs to S3:**
   ```bash
   aws s3 cp document.pdf s3://idp-wwso-input-files/input-pdfs/
   ```

2. **Run Extractor Agent:**
   - Trigger the agent via UI or API
   - Monitors: Batch processes all PDFs
   - Output: JSON files in `s3://idp-wwso-output/extracted-data/`

3. **Run Database Agent:**
   - Trigger the agent via UI or API
   - Creates DynamoDB table if needed
   - Imports all JSON files to DynamoDB

4. **Use Quality Check Agent:**
   - Ask questions about the data
   - Validate correct extractions
   - Update incorrect extractions

### Example Session

```
User: "Start extraction"
Extractor Agent: 
  📂 Found 3 PDF files
  ✅ Processed document1.pdf -> abc-123
  ✅ Processed document2.pdf -> def-456
  ✅ Processed document3.pdf -> ghi-789

User: "Import to database"
Database Agent:
  ✅ Created table 'IDP_Agent'
  ✅ Imported 3 documents

User: "What is the patient name in document abc-123?"
Quality Check Agent:
  The patient name is "John Doe" (confidence: 0.95, validated: false)

User: "validate patient_name for document abc-123"
Quality Check Agent:
  ✅ Successfully validated patient_name

User: "update phone to 555-9999 for document abc-123"
Quality Check Agent:
  ✅ Successfully updated phone
  ✓ Field marked as validated
```

---

## Configuration

### Environment Variables

Each agent supports these environment variables:

```bash
# AWS Configuration
export AWS_REGION=us-east-1
export AWS_PROFILE=your-profile  # Optional

# S3 Configuration (for Extractor Agent)
export INPUT_BUCKET=idp-wwso-input-files
export OUTPUT_BUCKET=idp-wwso-output

# DynamoDB Configuration (for Database & Quality Check Agents)
export DYNAMODB_TABLE=IDP_Agent
```

### Customization

To modify bucket names or table names, edit the configuration at the top of each agent file:

**extractor_agent.py:**
```python
INPUT_BUCKET = "your-input-bucket"
OUTPUT_BUCKET = "your-output-bucket"
INPUT_PREFIX = "input-pdfs/"
OUTPUT_PREFIX = "extracted-data/"
```

**database_agent.py & quality_check_agent.py:**
```python
DYNAMODB_TABLE_NAME = "Your_Table_Name"
PRIMARY_KEY = "document_id"
```

---

## Troubleshooting

### Extractor Agent Issues

**No files found:**
- Check S3 bucket name and prefix
- Verify PDFs are in `input-pdfs/` folder
- Check AWS credentials

**BDA MCP connection failed:**
- Ensure `uvx` is installed
- Check AWS region configuration
- Verify Bedrock Data Automation access

### Database Agent Issues

**Table creation failed:**
- Check IAM permissions for DynamoDB
- Verify table doesn't already exist with different schema
- Check AWS region

**Import failed:**
- Verify JSON files exist in S3
- Check JSON format is valid
- Review CloudWatch logs

### Quality Check Agent Issues

**No documents found:**
- Run Database Agent first
- Check DynamoDB table name
- Verify table has data

**Update/Validate failed:**
- Check document_id is correct (UUID format)
- Ensure field name matches exactly
- Review command syntax

---

## Advanced Usage

### Batch Processing Schedule

Use EventBridge to schedule automatic processing:

```yaml
# EventBridge Rule (pseudo-code)
Schedule: rate(1 hour)
Actions:
  1. Trigger Extractor Agent
  2. Wait 5 minutes
  3. Trigger Database Agent
```

### Data Quality Dashboard

Query DynamoDB to create a dashboard:

```python
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('IDP_Agent')

# Get validation statistics
response = table.scan()
total = len(response['Items'])
validated = sum(1 for item in response['Items'] 
                if any(field.get('validated', False) 
                      for field in item['extracted_fields'].values()))

print(f"Validation Rate: {validated/total*100:.1f}%")
```

### Export to CSV

```python
import boto3
import csv

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('IDP_Agent')

response = table.scan()

with open('extracted_data.csv', 'w') as f:
    writer = csv.writer(f)
    # Write headers and data
    for item in response['Items']:
        # Process and write rows
        pass
```

---

## API Reference

### Extractor Agent API

**Endpoint:** `/invocations`

**Payload:**
```json
{
  "prompt": "Start extraction",
  "sessionId": "optional-session-id"
}
```

### Database Agent API

**Endpoint:** `/invocations`

**Payload:**
```json
{
  "prompt": "Import data",
  "sessionId": "optional-session-id"
}
```

### Quality Check Agent API

**Endpoint:** `/invocations`

**Payload (Query):**
```json
{
  "prompt": "What is the patient name?",
  "sessionId": "session-id"
}
```

**Payload (Validate):**
```json
{
  "prompt": "validate phone for document abc-123",
  "sessionId": "session-id"
}
```

**Payload (Update):**
```json
{
  "prompt": "update phone to 555-9999 for document abc-123",
  "sessionId": "session-id"
}
```

---

## Cost Optimization

- **S3:** Use S3 Lifecycle policies to archive old files
- **DynamoDB:** On-demand billing scales with usage
- **Bedrock:** Batch process to minimize API calls
- **BDA MCP:** Process documents efficiently to reduce token usage

---

## Security Best Practices

1. **IAM Roles:** Use least-privilege access
2. **S3 Encryption:** Enable server-side encryption
3. **DynamoDB:** Enable point-in-time recovery
4. **VPC:** Deploy in private subnets if handling PHI/PII
5. **Audit:** Enable CloudTrail logging

---

## Support

For issues or questions:
1. Check CloudWatch Logs for each agent
2. Review this guide's troubleshooting section
3. Verify AWS permissions and configurations
4. Check the main README.md for project updates
