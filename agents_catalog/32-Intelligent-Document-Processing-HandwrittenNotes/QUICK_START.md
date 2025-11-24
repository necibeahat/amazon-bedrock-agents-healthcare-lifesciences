# Quick Start Guide - Three-Agent IDP System

## Overview

Three independent agents that handle document processing, storage, and quality checking:

1. **Extractor Agent** - Processes PDFs → JSON
2. **Database Agent** - JSON → DynamoDB  
3. **Quality Check Agent** - Query & Validate data

## Setup (One-Time)

```bash
# 1. Create S3 buckets
aws s3 mb s3://idp-wwso-input-files
aws s3 mb s3://idp-wwso-output

# 2. Upload PDFs to input folder
aws s3 cp your-document.pdf s3://idp-wwso-input-files/input-pdfs/
```

## Usage Flow

### Step 1: Extract Documents

**Trigger Extractor Agent:**
```
Prompt: "Start extraction"
```

**Output:**
- Processes all PDFs in `s3://idp-wwso-input-files/input-pdfs/`
- Saves JSON to `s3://idp-wwso-output/extracted-data/`
- Each document gets a unique UUID

### Step 2: Import to Database

**Trigger Database Agent:**
```
Prompt: "Import data"
```

**Output:**
- Creates DynamoDB table `IDP_Agent` if needed
- Imports all JSON files
- Adds `validated: false` to all fields

### Step 3: Query & Validate

**Trigger Quality Check Agent:**

**Ask questions:**
```
"What is the patient name?"
"List all unvalidated fields"
"Show fields with low confidence"
```

**Validate correct extraction:**
```
"validate phone for document abc-123-def"
```

**Update incorrect extraction:**
```
"update phone to 555-9999 for document abc-123-def"
```

## Running the Application

### Option 1: Unified Orchestrator UI (Recommended)

Run the orchestrator app for a complete workflow interface:

```bash
streamlit run app_orchestrator.py
```

**Features:**
- 🔄 **Sequential Processing Tab** - Run all three agents automatically
- 1️⃣ **Extractor Agent Tab** - Trigger extraction independently
- 2️⃣ **Database Agent Tab** - Trigger database import independently  
- 3️⃣ **Quality Check Agent Tab** - Interactive chat for queries and validation

**Setup:**
1. Configure agent ARNs in the sidebar
2. Use "Sequential Processing" to run all agents
3. Or trigger each agent independently in their tabs

### Option 2: Individual Agent Deployment

Deploy and run each agent separately:

```bash
# Deploy agents to Bedrock AgentCore
cd agent
uv run agentcore configure -e extractor_agent.py
uv run agentcore launch

# Repeat for database_agent.py and quality_check_agent.py
```

## Agent Files

- `agent/extractor_agent.py` - Document extraction
- `agent/database_agent.py` - Database import
- `agent/quality_check_agent.py` - Query & validate
- `app_orchestrator.py` - Unified Streamlit UI (NEW)

## Configuration

Edit these constants at the top of each file:

```python
# Extractor Agent
INPUT_BUCKET = "idp-wwso-input-files"
OUTPUT_BUCKET = "idp-wwso-output"

# Database & Quality Check Agents
DYNAMODB_TABLE_NAME = "IDP_Agent"
```

## Data Flow

```
PDF Files (S3)
    ↓
Extractor Agent (BDA MCP)
    ↓
JSON Files (S3)
    ↓
Database Agent
    ↓
DynamoDB Table
    ↓
Quality Check Agent (Query/Update)
```

## Common Commands

### Upload new documents
```bash
aws s3 cp document.pdf s3://idp-wwso-input-files/input-pdfs/
```

### Check extraction output
```bash
aws s3 ls s3://idp-wwso-output/extracted-data/
```

### Query DynamoDB
```bash
aws dynamodb scan --table-name IDP_Agent --max-items 10
```

### View specific document
```bash
aws dynamodb get-item \
  --table-name IDP_Agent \
  --key '{"document_id": {"S": "your-uuid-here"}}'
```

## Troubleshooting

**Extractor fails:**
- Check S3 bucket exists
- Verify PDFs in `input-pdfs/` folder
- Check BDA MCP connectivity

**Database import fails:**
- Ensure JSON files exist in output bucket
- Check DynamoDB permissions
- Verify table doesn't have schema conflicts

**Quality check fails:**
- Run Database Agent first
- Check table name matches
- Verify data exists in DynamoDB

## Example Session

```
# 1. Upload PDFs
aws s3 cp form1.pdf s3://idp-wwso-input-files/input-pdfs/
aws s3 cp form2.pdf s3://idp-wwso-input-files/input-pdfs/

# 2. Extract
User: "Start extraction"
Agent: ✅ Processed 2 files

# 3. Import
User: "Import data"  
Agent: ✅ Imported 2 documents

# 4. Query
User: "List all patient names"
Agent: Document abc-123: John Doe
        Document def-456: Jane Smith

# 5. Validate
User: "validate patient_name for document abc-123"
Agent: ✅ Successfully validated

# 6. Update
User: "update phone to 555-8888 for document abc-123"
Agent: ✅ Successfully updated phone
```

## Next Steps

See `AGENTS_GUIDE.md` for:
- Detailed architecture
- Advanced usage
- API reference
- Security best practices
- Cost optimization
