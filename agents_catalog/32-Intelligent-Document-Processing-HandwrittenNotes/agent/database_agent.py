# Database Agent - Loads extracted data from S3 and stores in DynamoDB
# This agent creates/updates DynamoDB table with structured medical form data

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
import os
import boto3
import json
from datetime import datetime
from decimal import Decimal
from botocore.exceptions import ClientError

os.environ["BYPASS_TOOL_CONSENT"] = "true"

app = BedrockAgentCoreApp()

# S3 Configuration
INPUT_BUCKET = "idp-wwso-output"
INPUT_PREFIX = "extracted-data/"

# DynamoDB Configuration
DYNAMODB_TABLE_NAME = "IDP_Agent"
PRIMARY_KEY = "document_id"

def ensure_dynamodb_table(dynamodb_client):
    """Create DynamoDB table if it doesn't exist"""
    try:
        # Check if table exists
        dynamodb_client.describe_table(TableName=DYNAMODB_TABLE_NAME)
        return True, f"✅ Table '{DYNAMODB_TABLE_NAME}' already exists"
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            # Table doesn't exist, create it
            try:
                dynamodb_client.create_table(
                    TableName=DYNAMODB_TABLE_NAME,
                    KeySchema=[
                        {
                            'AttributeName': PRIMARY_KEY,
                            'KeyType': 'HASH'  # Partition key
                        }
                    ],
                    AttributeDefinitions=[
                        {
                            'AttributeName': PRIMARY_KEY,
                            'AttributeType': 'S'  # String
                        }
                    ],
                    BillingMode='PAY_PER_REQUEST'  # On-demand billing
                )
                
                # Wait for table to be created
                waiter = dynamodb_client.get_waiter('table_exists')
                waiter.wait(TableName=DYNAMODB_TABLE_NAME)
                
                return True, f"✅ Created new table '{DYNAMODB_TABLE_NAME}'"
            except Exception as create_error:
                return False, f"❌ Error creating table: {str(create_error)}"
        else:
            return False, f"❌ Error checking table: {str(e)}"

def convert_floats_to_decimal(obj):
    """
    Recursively convert all float values to Decimal for DynamoDB compatibility
    DynamoDB does not support float types, only Decimal
    """
    if isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_floats_to_decimal(value) for key, value in obj.items()}
    elif isinstance(obj, float):
        # Convert float to Decimal, handling special cases
        if str(obj) in ['inf', '-inf', 'nan']:
            return str(obj)  # Convert special floats to strings
        return Decimal(str(obj))
    else:
        return obj

def process_extracted_fields(extracted_data):
    """Process extracted fields to ensure each has a 'validated' field"""
    processed_fields = {}
    
    if isinstance(extracted_data, dict):
        extracted_fields = extracted_data.get('extracted_fields', {})
        
        for field_name, field_data in extracted_fields.items():
            if isinstance(field_data, dict):
                # Ensure validated field exists
                if 'validated' not in field_data:
                    field_data['validated'] = False
                processed_fields[field_name] = field_data
            else:
                # If field_data is not a dict, wrap it
                processed_fields[field_name] = {
                    'value': str(field_data),
                    'confidence': Decimal('0.0'),
                    'validated': False
                }
    
    return processed_fields

@app.entrypoint
async def database_agent(payload):
    """
    Database Agent that loads extracted JSON data from S3 
    and stores it in DynamoDB with proper schema
    """
    user_prompt = payload.get("prompt", "")
    session_id = payload.get("sessionId", "default")
    
    try:
        yield "💾 Starting Database Agent...\n\n"
        
        # Initialize AWS clients
        s3_client = boto3.client('s3')
        dynamodb_client = boto3.client('dynamodb')
        dynamodb_resource = boto3.resource('dynamodb')
        
        # Ensure DynamoDB table exists
        yield "🔍 Checking DynamoDB table...\n"
        table_exists, message = ensure_dynamodb_table(dynamodb_client)
        yield f"{message}\n\n"
        
        if not table_exists:
            return
        
        table = dynamodb_resource.Table(DYNAMODB_TABLE_NAME)
        
        # List JSON files in S3 output bucket
        yield f"📂 Scanning S3 bucket: s3://{INPUT_BUCKET}/{INPUT_PREFIX}\n\n"
        
        try:
            response = s3_client.list_objects_v2(
                Bucket=INPUT_BUCKET,
                Prefix=INPUT_PREFIX
            )
            
            if 'Contents' not in response:
                yield "❌ No files found in S3 bucket\n"
                return
            
            json_files = [obj['Key'] for obj in response['Contents'] 
                         if obj['Key'].lower().endswith('.json')]
            
            if not json_files:
                yield "❌ No JSON files found in S3 bucket\n"
                return
            
            yield f"✅ Found {len(json_files)} JSON file(s) to process\n\n"
            
        except Exception as e:
            yield f"❌ Error accessing S3 bucket: {str(e)}\n"
            return
        
        # Process each JSON file
        processed_count = 0
        failed_count = 0
        
        for idx, json_key in enumerate(json_files, 1):
            try:
                filename = os.path.basename(json_key)
                yield f"📄 Processing file {idx}/{len(json_files)}: {filename}\n"
                
                # Read JSON from S3
                response = s3_client.get_object(Bucket=INPUT_BUCKET, Key=json_key)
                json_content = response['Body'].read().decode('utf-8')
                data = json.loads(json_content)
                
                # Extract document information
                document_id = data.get('document_id')
                if not document_id:
                    yield f"  ⚠️  Skipping: No document_id found\n\n"
                    failed_count += 1
                    continue
                
                source_file = data.get('source_file', '')
                extraction_timestamp = data.get('extraction_timestamp', '')
                extracted_data = data.get('extracted_data', {})
                
                # Process extracted fields to ensure validated field exists
                processed_fields = process_extracted_fields(extracted_data)
                
                # Prepare DynamoDB item
                dynamodb_item = {
                    'document_id': document_id,
                    'source_file': source_file,
                    'extraction_timestamp': extraction_timestamp,
                    'database_import_timestamp': datetime.utcnow().isoformat(),
                    'extracted_fields': processed_fields,
                    'metadata': extracted_data.get('metadata', {})
                }
                
                # Convert all floats to Decimal for DynamoDB compatibility
                dynamodb_item = convert_floats_to_decimal(dynamodb_item)
                
                # Store in DynamoDB
                table.put_item(Item=dynamodb_item)
                
                yield f"  ✅ Saved to DynamoDB (document_id: {document_id})\n"
                yield f"  📊 Fields stored: {len(processed_fields)}\n\n"
                
                processed_count += 1
                
            except Exception as e:
                yield f"  ❌ Error processing {filename}: {str(e)}\n\n"
                failed_count += 1
                continue
        
        # Summary
        yield "\n" + "="*50 + "\n"
        yield f"✅ Database import completed!\n\n"
        yield f"📊 Summary:\n"
        yield f"  - Total files: {len(json_files)}\n"
        yield f"  - Successfully imported: {processed_count}\n"
        yield f"  - Failed: {failed_count}\n"
        yield f"  - DynamoDB Table: {DYNAMODB_TABLE_NAME}\n\n"
        
        # Show sample query
        yield "💡 You can now use the Quality Check Agent to:\n"
        yield "  - Query extracted data\n"
        yield "  - Validate field values\n"
        yield "  - Update incorrect extractions\n"
    
    except Exception as e:
        import traceback
        yield f"❌ Error: {str(e)}\n"
        yield f"Traceback: {traceback.format_exc()}\n"


if __name__ == "__main__":
    app.run()
