# IDP Frontend - Quick Start Guide

Get up and running with the IDP Frontend Application in 5 minutes!

## Prerequisites Checklist

- [ ] Python 3.9+ installed
- [ ] AWS CLI configured with credentials
- [ ] Access to AWS Bedrock AgentCore
- [ ] S3 buckets created or permissions to create them
- [ ] Agents deployed (Extractor, Database, Quality Check)

## Installation (2 minutes)

### Step 1: Install Dependencies

```bash
cd agents_catalog/32-Intelligent-Document-Processing-HandwrittenNotes
pip install -r requirements_frontend.txt
```

### Step 2: Set Environment Variables

```bash
export AWS_REGION="us-east-1"
export AWS_PROFILE="your-profile"  # Optional if using named profiles
```

### Step 3: Verify AWS Setup

```bash
# Test AWS connectivity
aws s3 ls s3://idp-wwso-input-files --region us-east-1
aws s3 ls s3://idp-wwso-output --region us-east-1
aws dynamodb describe-table --table-name IDP_Agent --region us-east-1
```

## Launch the Application (30 seconds)

```bash
streamlit run app_idp_frontend.py
```

The app opens automatically at http://localhost:8501

## Your First Document Processing (3 minutes)

### 1. Upload a Document (30 seconds)

1. Go to **"📤 Upload & Extract"** tab
2. Click **"Browse files"**
3. Select a PDF file (e.g., medical intake form)
4. Select **"Extractor Agent"** from dropdown
5. Click **"🚀 Upload & Extract"**

**Expected Output:**
```
✅ Successfully uploaded 1 file(s) to S3
🔄 Starting extraction process...
✅ Extraction completed!
```

### 2. Validate Extracted Data (1 minute)

1. Go to **"✅ Validate & Review"** tab
2. Select your uploaded document
3. Review the extracted fields:
   - 🟢 Green = High confidence (>80%)
   - 🟡 Yellow = Medium confidence (50-80%)
   - 🔴 Red = Low confidence (<50%)
4. For any incorrect fields:
   - Edit the value
   - Click **"💾 Update"**
5. For correct fields:
   - Click **"✓ Validate"**

**Tip:** Use **"✓ Validate All High Confidence"** to bulk-validate green fields!

### 3. Query Your Documents (1 minute)

1. Go to **"💬 Q&A"** tab
2. Select **"Quality Check Agent"**
3. Type a question like:
   - "What information was extracted?"
   - "Which fields have low confidence?"
   - "Show me the patient's contact information"
4. Get instant AI-powered answers!

## Common Quick Start Issues

### Issue: "No agent runtimes found"

**Solution:**
```bash
# Check agents are deployed
aws bedrock-agentcore-control list-agent-runtimes --region us-east-1

# If empty, deploy agents first:
cd agent
python -m bedrock_agentcore.runtime.agent extractor_agent
```

### Issue: "S3 bucket doesn't exist"

**Solution:**
```bash
# Create buckets
aws s3 mb s3://idp-wwso-input-files --region us-east-1
aws s3 mb s3://idp-wwso-output --region us-east-1
```

### Issue: "DynamoDB table not found"

**Solution:**
This is normal! The table will be created automatically when you first run the Database Agent or validate documents.

## Configuration Quick Reference

### AWS Resource Names (Edit in `app_idp_frontend.py` if needed)

```python
S3_INPUT_BUCKET = "idp-wwso-input-files"      # Line 94
S3_OUTPUT_BUCKET = "idp-wwso-output"          # Line 96
DYNAMODB_TABLE_NAME = "IDP_Agent"             # Line 97
AWS_REGION = "us-east-1"                       # Line 98
```

### Agent Selection

The app automatically discovers deployed agents by name:
- **Extractor agents**: Must include "extractor" in name
- **Q&A agents**: Must include "quality" or "qa" in name

## Testing with Sample Data

Use the included sample file:

```bash
# Copy sample to test location
cp data/Sample_Filled_MedicalIntakeForm.pdf ~/Desktop/test.pdf

# Upload via UI or command line
aws s3 cp ~/Desktop/test.pdf s3://idp-wwso-input-files/input-pdfs/
```

## Next Steps

Once you've completed your first processing:

1. **Explore Features:** Try all three tabs
2. **Review Docs:** Check [FRONTEND_README.md](FRONTEND_README.md) for details
3. **Customize:** Adjust confidence thresholds or UI styling
4. **Integrate:** Connect to your existing workflows

## Quick Command Reference

```bash
# Start the app
streamlit run app_idp_frontend.py

# Start on different port
streamlit run app_idp_frontend.py --server.port 8502

# Start without auto-opening browser
streamlit run app_idp_frontend.py --server.headless true

# View Streamlit logs
streamlit run app_idp_frontend.py --logger.level debug

# Install additional dependencies
pip install streamlit --upgrade
```

## Keyboard Shortcuts in the UI

- `Ctrl/Cmd + Enter` - Submit chat message
- `Ctrl/Cmd + K` - Clear cache and refresh
- `R` - Rerun app (when in development mode)

## Development Mode

For development with auto-reload:

```bash
streamlit run app_idp_frontend.py --server.runOnSave true
```

## Production Deployment

For production use:

```bash
# Set environment
export STREAMLIT_SERVER_ENABLE_CORS=false
export STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=true

# Run with config
streamlit run app_idp_frontend.py \
  --server.port 8501 \
  --server.address 0.0.0.0 \
  --server.headless true
```

## Getting Help

- **UI Issues:** Check browser console (F12)
- **AWS Errors:** Check CloudWatch logs
- **Agent Issues:** Review extraction logs in UI
- **Documentation:** See [FRONTEND_README.md](FRONTEND_README.md)

## Performance Tips

1. **Use bulk validation** for multiple high-confidence fields
2. **Export validated data** regularly to avoid re-work
3. **Clear chat history** if Q&A responses slow down
4. **Refresh agent list** if new agents don't appear

## Success Metrics

After your first session, you should have:
- ✅ At least 1 document uploaded and extracted
- ✅ Majority of fields validated
- ✅ Successfully queried your documents
- ✅ Exported validated data to JSON

## What's Next?

- Process multiple documents simultaneously
- Set up automated workflows
- Integrate with downstream systems
- Create custom validation rules
- Build analytics dashboards

---

**Stuck? Common fixes:**
```bash
# Restart Streamlit
Ctrl+C  # Stop
streamlit run app_idp_frontend.py  # Start again

# Clear Streamlit cache
rm -rf ~/.streamlit/cache

# Reset Python environment
pip install -r requirements_frontend.txt --force-reinstall
```

**Still need help?** Check the [full documentation](FRONTEND_README.md) or agent logs in the UI.

Happy processing! 🚀
