# Extractor Agent - Processes documents from S3 using BDA MCP and saves extracted data to S3
# This agent handles batch processing of PDF files and outputs structured JSON data

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
from mcp import stdio_client, StdioServerParameters
from strands.tools.mcp import MCPClient
import os
import boto3
import json
from datetime import datetime
import uuid

os.environ["BYPASS_TOOL_CONSENT"] = "true"

app = BedrockAgentCoreApp()

# S3 Configuration
INPUT_BUCKET = "idp-wwso-input-files"
INPUT_PREFIX = "input-pdfs/"
OUTPUT_BUCKET = "idp-wwso-output"
OUTPUT_PREFIX = "extracted-data/"

BDA_PROJECT_ARN = os.environ.get("BDA_PROJECT_ARN", "arn:aws:bedrock:us-east-1:774305571746:data-automation-project/ef41d092d129")

@app.entrypoint
async def extractor_agent(payload):
    """
    Extractor Agent that processes PDF documents from S3 using BDA MCP
    and saves structured JSON output to S3
    """
    user_prompt = payload.get("prompt", "")
    session_id = payload.get("sessionId", "default")
    
    try:
        yield "🔍 Starting Document Extraction Agent...\n\n"
        
        s3_client = boto3.client('s3')
        
        # List PDF files in input bucket
        yield f"📂 Scanning input bucket: s3://{INPUT_BUCKET}/{INPUT_PREFIX}\n\n"
        
        try:
            response = s3_client.list_objects_v2(
                Bucket=INPUT_BUCKET,
                Prefix=INPUT_PREFIX
            )
            
            if 'Contents' not in response:
                yield "❌ No files found in input bucket\n"
                return
            
            pdf_files = [obj['Key'] for obj in response['Contents'] 
                        if obj['Key'].lower().endswith('.pdf')]
            
            if not pdf_files:
                yield "❌ No PDF files found in input bucket\n"
                return
            
            yield f"✅ Found {len(pdf_files)} PDF file(s) to process\n\n"
            
        except Exception as e:
            yield f"❌ Error accessing S3 bucket: {str(e)}\n"
            return
        
        # Initialize Bedrock model
        bedrock_model = BedrockModel(
            model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            temperature=0.2,
        )
        
        # Initialize MCP client
        aws_bda_client = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="uvx",
                    args=["awslabs.aws-bedrock-data-automation-mcp-server@latest"],
                    env={
                        "AWS_REGION": os.environ.get("AWS_REGION", "us-east-1"),
                        "AWS_BUCKET_NAME": INPUT_BUCKET,
                        "BASE_DIR": "/tmp",
                        "FASTMCP_LOG_LEVEL": "ERROR"
                    }
                )
            )
        )
        
        yield "🔧 Connecting to BDA MCP server...\n\n"
        
        with aws_bda_client:
            tools = aws_bda_client.list_tools_sync()
            yield f"✅ Connected! Found {len(tools)} tools\n\n"
            
            # Process each PDF file
            processed_files = []
            
            for idx, pdf_key in enumerate(pdf_files, 1):
                try:
                    filename = os.path.basename(pdf_key)
                    yield f"📄 Processing file {idx}/{len(pdf_files)}: {filename}\n"
                    
                    # Download file to /tmp
                    local_file = f"/tmp/{filename}"
                    s3_client.download_file(INPUT_BUCKET, pdf_key, local_file)
                    yield f"  ⬇️  Downloaded to {local_file}\n"
                    
                    # Extract data using BDA MCP
                    idp_agent = Agent(
                        system_prompt=(
                            f"""You are an AI assistant with expertise in parsing handwritten notes and complex medical documents. 
                            You have access to the analyzeasset tool from the AWS Bedrock Data Automation MCP server.
                            
                            Use the analyzeasset tool to extract information from documents with these parameters:
                            - assetPath: the file path to analyze
                            - projectArn: {BDA_PROJECT_ARN}
                            
                            Extract all questions and answers provided in the document. 
                            For checkboxes, mark 'true' if selected, 'false' otherwise.
                            Include confidence scores for each extracted field (0-1 scale).
                            Return results as a valid JSON object with the following structure:
                            {{
                                "extracted_fields": {{
                                    "field_name": {{
                                        "value": "extracted_value",
                                        "confidence": 0.95,
                                        "validated": false
                                    }}
                                }},
                                "metadata": {{
                                    "extraction_date": "ISO timestamp",
                                    "document_type": "medical_intake_form"
                                }}
                            }}"""
                        ),
                        model=bedrock_model,
                        tools=tools
                    )
                    
                    response = idp_agent(
                        f"Use the analyzeasset tool to analyze the document at {local_file}. "
                        f"Make sure to provide the projectArn parameter with value: {BDA_PROJECT_ARN}. "
                        f"Extract all information and return it in JSON format."
                    )
                    response_text = str(response)
                    
                    yield f"  ✅ Extraction completed\n"
                    
                    # Generate unique document ID
                    document_id = str(uuid.uuid4())
                    
                    # Parse and structure the extracted data
                    try:
                        # Try to extract JSON from response
                        import re
                        json_match = re.search(r'\{[\s\S]*\}', response_text)
                        if json_match:
                            extracted_data = json.loads(json_match.group())
                        else:
                            # If no JSON found, wrap the response
                            extracted_data = {
                                "extracted_fields": {},
                                "raw_response": response_text
                            }
                    except:
                        extracted_data = {
                            "extracted_fields": {},
                            "raw_response": response_text
                        }
                    
                    # Add metadata
                    output_data = {
                        "document_id": document_id,
                        "source_file": f"s3://{INPUT_BUCKET}/{pdf_key}",
                        "extraction_timestamp": datetime.utcnow().isoformat(),
                        "extracted_data": extracted_data
                    }
                    
                    # Save to S3 output bucket
                    output_key = f"{OUTPUT_PREFIX}{document_id}.json"
                    s3_client.put_object(
                        Bucket=OUTPUT_BUCKET,
                        Key=output_key,
                        Body=json.dumps(output_data, indent=2),
                        ContentType='application/json'
                    )
                    
                    yield f"  💾 Saved to s3://{OUTPUT_BUCKET}/{output_key}\n\n"
                    
                    processed_files.append({
                        "document_id": document_id,
                        "source_file": filename,
                        "output_location": f"s3://{OUTPUT_BUCKET}/{output_key}"
                    })
                    
                    # Clean up local file
                    if os.path.exists(local_file):
                        os.remove(local_file)
                    
                except Exception as e:
                    yield f"  ❌ Error processing {filename}: {str(e)}\n\n"
                    continue
            
            # Summary
            yield "\n" + "="*50 + "\n"
            yield f"✅ Batch processing completed!\n\n"
            yield f"📊 Summary:\n"
            yield f"  - Total files: {len(pdf_files)}\n"
            yield f"  - Successfully processed: {len(processed_files)}\n"
            yield f"  - Failed: {len(pdf_files) - len(processed_files)}\n\n"
            
            if processed_files:
                yield "📋 Processed documents:\n"
                for file_info in processed_files:
                    yield f"  - {file_info['source_file']}: {file_info['document_id']}\n"
    
    except Exception as e:
        import traceback
        yield f"❌ Error: {str(e)}\n"
        yield f"Traceback: {traceback.format_exc()}\n"


if __name__ == "__main__":
    app.run()
