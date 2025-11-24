# IDP Frontend Application Guide

## Overview

The **IDP Frontend Application** (`app_idp_frontend.py`) is a comprehensive Streamlit-based user interface for the Intelligent Document Processing (IDP) system. It provides an end-to-end workflow for document extraction, validation, and querying.

## Features

### 1. **Document Upload & Extraction** 📤
- Upload multiple PDF documents simultaneously
- Automatic upload to S3 input bucket
- Integration with Bedrock Agent extractor for document processing
- Real-time extraction progress monitoring
- Extraction log viewing

### 2. **Extraction Visualization & Validation** ✅
- View all extracted documents from DynamoDB
- Interactive field-by-field validation interface
- Confidence score visualization with color coding:
  - 🟢 Green: High confidence (>80%)
  - 🟡 Yellow: Medium confidence (50-80%)
  - 🔴 Red: Low confidence (<50%)
- Edit and update extracted field values
- Mark fields as validated
- Bulk validation for high-confidence fields
- Export validated data to JSON
- Real-time statistics dashboard

### 3. **Document Q&A** 💬
- Ask natural language questions about extracted documents
- Integration with Quality Check Agent for intelligent responses
- Chat-based interface with conversation history
- Document summary viewer
- Example questions for guidance

### 4. **Human-in-the-Loop Validation** 🔄
- Review AI-extracted data before saving to DynamoDB
- Manual correction of extraction errors
- Confidence-based validation workflow
- Validation status tracking per field
- Audit trail with timestamps

### 5. **DynamoDB Integration** 💾
- Automatic persistence of validated data
- Real-time updates to database
- Support for complex nested field structures
- Decimal type handling for confidence scores
- Session-based document management

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                        │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │  Upload &  │  │ Validation & │  │   Document Q&A   │    │
│  │  Extract   │  │    Review    │  │                  │    │
│  └─────┬──────┘  └──────┬───────┘  └────────┬─────────┘    │
└────────┼─────────────────┼──────────────────┼──────────────┘
         │                 │                  │
         ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                      AWS Services                            │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ S3 Input │  │   DynamoDB   │  │ Bedrock AgentCore  │    │
│  │  Bucket  │  │  IDP_Agent   │  │   - Extractor      │    │
│  │          │  │    Table     │  │   - Quality Check  │    │
│  └──────────┘  └──────────────┘  └────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites
- Python 3.9 or higher
- AWS credentials configured
- Access to Bedrock AgentCore
- S3 buckets created (`idp-wwso-input-files`, `idp-wwso-output`)
- DynamoDB table will be created automatically

### Install Dependencies

```bash
cd agents_catalog/32-Intelligent-Document-Processing-HandwrittenNotes
pip install -r requirements_frontend.txt
```

## Configuration

### Environment Variables

```bash
export AWS_REGION="us-east-1"  # Optional, defaults to us-east-1
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
```

### AWS Resources

The application expects the following AWS resources:

1. **S3 Buckets:**
   - Input: `idp-wwso-input-files` (with prefix `input-pdfs/`)
   - Output: `idp-wwso-output` (with prefix `extracted-data/`)

2. **DynamoDB Table:**
   - Name: `IDP_Agent`
   - Primary Key: `document_id` (String)
   - Billing Mode: Pay-per-request
   - *Note: Created automatically if doesn't exist*

3. **Bedrock Agents:**
   - Extractor Agent (deployed via AgentCore)
   - Quality Check Agent (deployed via AgentCore)

## Usage

### Starting the Application

```bash
streamlit run app_idp_frontend.py
```

The application will open in your default browser at `http://localhost:8501`

### Workflow

#### Step 1: Upload & Extract Documents

1. Navigate to the **"📤 Upload & Extract"** tab
2. Click **"Browse files"** and select one or more PDF documents
3. Select the **Extractor Agent** from the dropdown
4. Click **"🚀 Upload & Extract"**
5. Monitor the extraction process in the log viewer
6. Wait for confirmation message

#### Step 2: Validate Extracted Data

1. Navigate to the **"✅ Validate & Review"** tab
2. Select a document from the dropdown
3. Review document statistics:
   - Total fields extracted
   - Validation status
   - Average confidence score
4. For each field:
   - **Review** the extracted value
   - **Edit** if incorrect
   - Click **"💾 Update"** to save changes, or
   - Click **"✓ Validate"** to confirm without changes
5. Use **"✓ Validate All High Confidence"** for bulk validation
6. **Export** validated data as JSON if needed

#### Step 3: Query Documents

1. Navigate to the **"💬 Q&A"** tab
2. Select the **Quality Check Agent** from the dropdown
3. Review available documents in the expander
4. Type your question in the chat input
5. View AI-generated responses
6. Continue the conversation as needed

### Field Validation Examples

**Confidence Indicators:**
- 🟢 **95%** - High confidence, likely correct
- 🟡 **65%** - Medium confidence, review recommended
- 🔴 **30%** - Low confidence, manual verification required

**Validation Badges:**
- <span style="background-color: #28a745; color: white; padding: 2px 8px; border-radius: 12px;">✓ Validated</span> - Field confirmed as correct
- <span style="background-color: #ffc107; color: black; padding: 2px 8px; border-radius: 12px;">⚠ Pending</span> - Needs validation

## Features in Detail

### Document Extraction

The extraction process:
1. Uploads PDFs to S3 input bucket
2. Invokes the Extractor Agent via Bedrock AgentCore
3. Agent uses BDA MCP to analyze documents
4. Structured JSON output saved to S3 output bucket
5. Data ready for validation

### Validation Interface

Key capabilities:
- **Field-by-field review**: Each extracted field displayed separately
- **Inline editing**: Modify values directly in the UI
- **Confidence scoring**: Visual indicators for extraction quality
- **Validation tracking**: Clear status for each field
- **Bulk operations**: Validate multiple fields at once
- **Export functionality**: Download validated data

### Q&A System

Powered by the Quality Check Agent:
- **Contextual understanding**: Agent has access to all document data
- **Natural language queries**: Ask questions in plain English
- **Intelligent responses**: Leverages Claude Sonnet 4 for answers
- **Document context**: Queries across all extracted documents
- **Conversation memory**: Maintains chat history

### Human-in-the-Loop Process

The validation workflow ensures data quality:

1. **Initial Extraction**: AI extracts data with confidence scores
2. **Human Review**: User reviews all fields
3. **Correction**: User corrects any errors
4. **Validation**: User marks fields as validated
5. **Persistence**: Validated data saved to DynamoDB
6. **Audit Trail**: Timestamps and validation status tracked

## Data Schema

### DynamoDB Item Structure

```json
{
  "document_id": "uuid-string",
  "source_file": "s3://bucket/path/to/file.pdf",
  "extraction_timestamp": "2024-01-15T10:30:00",
  "database_import_timestamp": "2024-01-15T10:35:00",
  "last_updated": "2024-01-15T11:00:00",
  "extracted_fields": {
    "patient_name": {
      "value": "John Doe",
      "confidence": 0.95,
      "validated": true
    },
    "date_of_birth": {
      "value": "1980-05-15",
      "confidence": 0.88,
      "validated": true
    },
    "phone_number": {
      "value": "555-1234",
      "confidence": 0.65,
      "validated": false
    }
  },
  "metadata": {
    "extraction_date": "2024-01-15T10:30:00",
    "document_type": "medical_intake_form"
  }
}
```

## Troubleshooting

### Common Issues

**1. "No agent runtimes found"**
- Ensure agents are deployed via AgentCore
- Check AWS credentials have access to Bedrock
- Verify region is correct

**2. "DynamoDB table not found"**
- Run the Database Agent first to create the table
- Or manually create table with schema above

**3. "Error uploading to S3"**
- Check S3 bucket exists and is accessible
- Verify IAM permissions for S3 operations
- Ensure bucket name is correct in configuration

**4. "Error invoking agent"**
- Verify agent ARN is correct
- Check agent is in READY state
- Ensure AgentCore permissions are configured

### System Status Indicators

The sidebar shows real-time status:
- ✅ **AWS Connected**: AWS SDK initialized
- ✅ **S3 Input Bucket**: Bucket accessible
- ✅ **DynamoDB Table**: Table exists and accessible
- ⚠️ or ❌: Issues detected

## Advanced Features

### Bulk Validation

Automatically validate all fields with confidence > 80%:
```python
# Triggered via UI button
# Validates all high-confidence fields in one action
```

### Export Validated Data

Download validated document data:
- JSON format
- Includes all fields with validation status
- Preserves confidence scores
- Timestamped for audit trail

### Chat History

Q&A tab maintains conversation history:
- All questions and answers preserved
- Can reference previous queries
- Clear chat option available

## API Integration

### Invoking Agents Programmatically

```python
from app_idp_frontend import invoke_agent

response = invoke_agent(
    agent_arn="arn:aws:bedrock:...",
    prompt="Extract this document",
    session_id="unique-session-id"
)
```

### Updating Fields Programmatically

```python
from app_idp_frontend import update_field_in_dynamodb

success = update_field_in_dynamodb(
    document_id="doc-uuid",
    field_name="patient_name",
    new_value="Jane Doe",
    validated=True
)
```

## Performance Considerations

- **Caching**: AWS clients cached using `@st.cache_resource`
- **Lazy Loading**: Documents loaded on-demand
- **Pagination**: DynamoDB scan handles pagination automatically
- **Session State**: Chat history and UI state preserved

## Security Best Practices

1. **AWS Credentials**: Use IAM roles instead of access keys when possible
2. **Least Privilege**: Grant minimum required permissions
3. **Encryption**: Enable encryption at rest for DynamoDB and S3
4. **Audit Logging**: Enable CloudTrail for API calls
5. **Network Security**: Use VPC endpoints for AWS services

## Future Enhancements

Potential improvements:
- [ ] Batch document processing queue
- [ ] Custom confidence threshold configuration
- [ ] Multi-language support
- [ ] Advanced search and filtering
- [ ] Document comparison view
- [ ] Automated quality metrics dashboard
- [ ] Integration with external systems
- [ ] Role-based access control

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review agent logs in the UI
3. Verify AWS resource configuration
4. Check CloudWatch logs for agents

## License

This application is part of the Amazon Bedrock Agents for Healthcare and Life Sciences repository.

---

**Built with:**
- Streamlit for the UI framework
- AWS Bedrock AgentCore for AI capabilities
- DynamoDB for data persistence
- S3 for document storage
