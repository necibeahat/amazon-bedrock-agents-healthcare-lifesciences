# Extractor Agent Test Guide

This guide explains how to test the Extractor Agent using the provided test script.

## Overview

The `test_extractor_agent.py` script allows you to test the Extractor Agent's functionality in processing PDF documents from S3 using the AWS Bedrock Data Automation MCP server.

## Prerequisites

1. **AWS Credentials**: Configure AWS credentials with access to:
   - Amazon Bedrock (specifically Bedrock Data Automation)
   - S3 buckets
   - Appropriate IAM permissions

2. **Python Dependencies**: Ensure all required packages are installed:
   ```bash
   cd agents_catalog/32-Intelligent-Document-Processing-HandwrittenNotes
   pip install -r agent/requirements.txt
   ```

3. **S3 Buckets**: You need two S3 buckets:
   - Input bucket: `idp-wwso-input-files`
   - Output bucket: `idp-wwso-output`

4. **Test Documents**: Upload PDF files to test with

## Setup Instructions

### Step 1: Create S3 Buckets (if not already created)

```bash
# Create input bucket
aws s3 mb s3://idp-wwso-input-files

# Create output bucket
aws s3 mb s3://idp-wwso-output
```

### Step 2: Upload Sample PDF Documents

```bash
# Upload a sample PDF to the input folder
aws s3 cp your-sample.pdf s3://idp-wwso-input-files/input-pdfs/

# Verify the upload
aws s3 ls s3://idp-wwso-input-files/input-pdfs/
```

### Step 3: Set Environment Variables

```bash
# Set AWS region
export AWS_REGION=us-east-1

# Set BDA Project ARN
export BDA_PROJECT_ARN=arn:aws:bedrock:us-east-1:774305571746:data-automation-project/ef41d092d129
```

## Running the Test

### Basic Test Run

Run the test script to process all PDFs in the input bucket:

```bash
cd agents_catalog/32-Intelligent-Document-Processing-HandwrittenNotes/test
python test_extractor_agent.py
```

Or from the project root:

```bash
python agents_catalog/32-Intelligent-Document-Processing-HandwrittenNotes/test/test_extractor_agent.py
```

### View Setup Instructions

To view detailed setup instructions:

```bash
cd agents_catalog/32-Intelligent-Document-Processing-HandwrittenNotes/test
python test_extractor_agent.py --setup-instructions
```

### Run with Custom Environment Variables

```bash
cd agents_catalog/32-Intelligent-Document-Processing-HandwrittenNotes/test
AWS_REGION=us-west-2 BDA_PROJECT_ARN=your-project-arn python test_extractor_agent.py
```

## What the Test Does

The test script:

1. ✅ Imports and validates the extractor agent module
2. 📋 Displays configuration settings
3. 📂 Scans the S3 input bucket for PDF files
4. 🔧 Connects to the BDA MCP server
5. 📄 Processes each PDF file:
   - Downloads the file locally
   - Uses the `analyzeasset` tool with the BDA Project ARN
   - Extracts structured data
   - Saves results to the output S3 bucket
6. 📊 Provides a summary of processed files

## Expected Output

```
======================================================================
🧪 EXTRACTOR AGENT TEST
======================================================================
Start Time: 2025-11-24 20:37:00

✅ Successfully imported extractor_agent

📋 Configuration:
  AWS Region: us-east-1
  BDA Project ARN: arn:aws:bedrock:us-east-1:774305571746:data-automation-project/ef41d092d129
  Input Bucket: idp-wwso-input-files
  Output Bucket: idp-wwso-output

📦 Test Payload:
  Prompt: Process all PDF documents in the input bucket
  Session ID: test-session-20251124-203700

----------------------------------------------------------------------
🚀 Starting Extractor Agent...
----------------------------------------------------------------------

🔍 Starting Document Extraction Agent...

📂 Scanning input bucket: s3://idp-wwso-input-files/input-pdfs/

✅ Found 2 PDF file(s) to process

🔧 Connecting to BDA MCP server...

✅ Connected! Found 3 tools

📄 Processing file 1/2: sample-form.pdf
  ⬇️  Downloaded to /tmp/sample-form.pdf
  ✅ Extraction completed
  💾 Saved to s3://idp-wwso-output/extracted-data/abc-123-def.json

📄 Processing file 2/2: medical-notes.pdf
  ⬇️  Downloaded to /tmp/medical-notes.pdf
  ✅ Extraction completed
  💾 Saved to s3://idp-wwso-output/extracted-data/xyz-456-ghi.json

==================================================
✅ Batch processing completed!

📊 Summary:
  - Total files: 2
  - Successfully processed: 2
  - Failed: 0

📋 Processed documents:
  - sample-form.pdf: abc-123-def
  - medical-notes.pdf: xyz-456-ghi

----------------------------------------------------------------------
✅ Test completed successfully!
----------------------------------------------------------------------

End Time: 2025-11-24 20:38:45
```

## Verifying Results

After the test completes, verify the extracted data:

```bash
# List output files
aws s3 ls s3://idp-wwso-output/extracted-data/

# Download and view a result
aws s3 cp s3://idp-wwso-output/extracted-data/abc-123-def.json - | jq .
```

## Output Format

Each processed document generates a JSON file with this structure:

```json
{
  "document_id": "abc-123-def-456",
  "source_file": "s3://idp-wwso-input-files/input-pdfs/sample.pdf",
  "extraction_timestamp": "2025-11-24T20:37:30.123456",
  "extracted_data": {
    "extracted_fields": {
      "field_name": {
        "value": "extracted_value",
        "confidence": 0.95,
        "validated": false
      }
    },
    "metadata": {
      "extraction_date": "2025-11-24T20:37:30Z",
      "document_type": "medical_intake_form"
    }
  }
}
```

## Troubleshooting

### AWS Credentials Error
```
⚠️  Warning: AWS credentials not configured or invalid
```
**Solution**: Configure AWS credentials using `aws configure` or set environment variables.

### No Files Found
```
❌ No PDF files found in input bucket
```
**Solution**: Upload PDF files to `s3://idp-wwso-input-files/input-pdfs/`

### Import Error
```
❌ Failed to import extractor_agent
```
**Solution**: Ensure you're running from the correct directory and all dependencies are installed.

### BDA Connection Error
```
❌ Error connecting to BDA MCP server
```
**Solution**: 
- Verify `uvx` is installed: `uv --version`
- Check AWS permissions for Bedrock Data Automation
- Ensure the BDA Project ARN is correct

## Advanced Usage

### Testing with Specific Files

Modify the script to process specific files:

```python
# In test_extractor_agent.py, modify the payload
payload = {
    "prompt": "Process the medical form PDF",
    "sessionId": "custom-session-id",
    "specific_files": ["input-pdfs/medical-form.pdf"]
}
```

### Enabling Debug Logging

Set more verbose logging:

```bash
export FASTMCP_LOG_LEVEL=DEBUG
cd agents_catalog/32-Intelligent-Document-Processing-HandwrittenNotes/test
python test_extractor_agent.py
```

## Integration Testing

To test the full IDP pipeline:

1. Run the extractor agent test (this script)
2. Run the database agent to store extracted data
3. Run the quality check agent to validate results

See `QUICK_START.md` for full pipeline testing instructions.

## Support

For issues or questions:
- Check the main [README.md](../README.md)
- Review [AGENTS_GUIDE.md](../AGENTS_GUIDE.md)
- See [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md)
