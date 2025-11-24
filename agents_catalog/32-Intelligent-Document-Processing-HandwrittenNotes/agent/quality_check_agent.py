# Quality Check Agent - Queries DynamoDB data and allows validation/updates
# This agent answers questions about extracted data and enables field validation/updates

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
import os
import boto3
import json
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr

os.environ["BYPASS_TOOL_CONSENT"] = "true"

app = BedrockAgentCoreApp()

# DynamoDB Configuration
DYNAMODB_TABLE_NAME = "IDP_Agent"
PRIMARY_KEY = "document_id"

# Helper function to convert Decimal to native Python types
def decimal_to_native(obj):
    """Convert DynamoDB Decimal types to native Python types"""
    if isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    else:
        return obj

def get_all_documents(table):
    """Retrieve all documents from DynamoDB"""
    try:
        response = table.scan()
        items = response.get('Items', [])
        
        # Handle pagination if needed
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))
        
        return decimal_to_native(items)
    except Exception as e:
        return None

def get_document_by_id(table, document_id):
    """Retrieve a specific document from DynamoDB"""
    try:
        response = table.get_item(Key={PRIMARY_KEY: document_id})
        item = response.get('Item')
        return decimal_to_native(item) if item else None
    except Exception as e:
        return None

def update_field_value(table, document_id, field_name, new_value, validate=True):
    """Update a field value in DynamoDB and set validated to True"""
    try:
        # Get current item
        response = table.get_item(Key={PRIMARY_KEY: document_id})
        item = response.get('Item')
        
        if not item:
            return False, f"Document {document_id} not found"
        
        # Update the field
        extracted_fields = item.get('extracted_fields', {})
        
        if field_name not in extracted_fields:
            # Add new field
            extracted_fields[field_name] = {
                'value': new_value,
                'confidence': 1.0,  # Manual updates have high confidence
                'validated': True
            }
        else:
            # Update existing field
            extracted_fields[field_name]['value'] = new_value
            extracted_fields[field_name]['validated'] = True
            if validate:
                extracted_fields[field_name]['confidence'] = 1.0
        
        # Update in DynamoDB
        table.update_item(
            Key={PRIMARY_KEY: document_id},
            UpdateExpression='SET extracted_fields = :fields, last_updated = :timestamp',
            ExpressionAttributeValues={
                ':fields': extracted_fields,
                ':timestamp': datetime.utcnow().isoformat()
            }
        )
        
        return True, f"Successfully updated {field_name}"
    except Exception as e:
        return False, str(e)

def validate_field(table, document_id, field_name):
    """Mark a field as validated without changing its value"""
    try:
        response = table.get_item(Key={PRIMARY_KEY: document_id})
        item = response.get('Item')
        
        if not item:
            return False, f"Document {document_id} not found"
        
        extracted_fields = item.get('extracted_fields', {})
        
        if field_name not in extracted_fields:
            return False, f"Field {field_name} not found"
        
        # Mark as validated
        extracted_fields[field_name]['validated'] = True
        
        table.update_item(
            Key={PRIMARY_KEY: document_id},
            UpdateExpression='SET extracted_fields = :fields, last_updated = :timestamp',
            ExpressionAttributeValues={
                ':fields': extracted_fields,
                ':timestamp': datetime.utcnow().isoformat()
            }
        )
        
        return True, f"Successfully validated {field_name}"
    except Exception as e:
        return False, str(e)

@app.entrypoint
async def quality_check_agent(payload):
    """
    Quality Check Agent that queries DynamoDB data, answers questions,
    and allows users to validate or update field values
    """
    user_prompt = payload.get("prompt", "").strip()
    session_id = payload.get("sessionId", "default")
    
    try:
        # Initialize DynamoDB
        dynamodb_resource = boto3.resource('dynamodb')
        table = dynamodb_resource.Table(DYNAMODB_TABLE_NAME)
        
        # Check if user wants to update a field
        # Pattern: "update <field> to <value> for document <id>"
        # or: "validate <field> for document <id>"
        
        if "update" in user_prompt.lower():
            # Parse update command
            import re
            
            # Try patterns like: "update phone to 555-1234 for document abc123"
            update_pattern = r'update\s+([^\s]+)\s+to\s+(.+?)\s+(?:for|in)\s+document\s+([a-zA-Z0-9\-]+)'
            match = re.search(update_pattern, user_prompt.lower())
            
            if match:
                field_name = match.group(1)
                new_value = match.group(2).strip()
                document_id = match.group(3)
                
                yield f"🔄 Updating field '{field_name}' to '{new_value}' for document {document_id}...\n\n"
                
                success, message = update_field_value(table, document_id, field_name, new_value, validate=True)
                
                if success:
                    yield f"✅ {message}\n"
                    yield f"✓ Field marked as validated\n"
                else:
                    yield f"❌ Update failed: {message}\n"
                return
        
        if "validate" in user_prompt.lower():
            # Parse validate command
            import re
            
            # Pattern: "validate phone for document abc123"
            validate_pattern = r'validate\s+([^\s]+)\s+(?:for|in)\s+document\s+([a-zA-Z0-9\-]+)'
            match = re.search(validate_pattern, user_prompt.lower())
            
            if match:
                field_name = match.group(1)
                document_id = match.group(2)
                
                yield f"✓ Validating field '{field_name}' for document {document_id}...\n\n"
                
                success, message = validate_field(table, document_id, field_name)
                
                if success:
                    yield f"✅ {message}\n"
                else:
                    yield f"❌ Validation failed: {message}\n"
                return
        
        # For general queries, get all data and use AI to answer
        yield "🔍 Querying DynamoDB data...\n\n"
        
        documents = get_all_documents(table)
        
        if not documents:
            yield "❌ No documents found in database. Please run the Database Agent first.\n"
            return
        
        yield f"✅ Found {len(documents)} document(s)\n\n"
        
        # Prepare context for AI
        context_data = []
        for doc in documents:
            doc_summary = {
                'document_id': doc.get('document_id'),
                'source_file': doc.get('source_file', 'Unknown'),
                'extraction_timestamp': doc.get('extraction_timestamp', ''),
                'fields': {}
            }
            
            extracted_fields = doc.get('extracted_fields', {})
            for field_name, field_data in extracted_fields.items():
                if isinstance(field_data, dict):
                    doc_summary['fields'][field_name] = {
                        'value': field_data.get('value'),
                        'confidence': field_data.get('confidence', 0),
                        'validated': field_data.get('validated', False)
                    }
            
            context_data.append(doc_summary)
        
        # Initialize Bedrock model for Q&A
        bedrock_model = BedrockModel(
            model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            temperature=0.3,
        )
        
        # Create Q&A agent
        qa_agent = Agent(
            system_prompt=f"""You are an AI assistant helping users query and understand medical intake form data stored in DynamoDB.

Available data from {len(documents)} document(s):
{json.dumps(context_data, indent=2)}

Your tasks:
1. Answer user questions about the extracted data accurately
2. Help users identify which fields need validation
3. Provide clear instructions for updating fields
4. Highlight fields with low confidence scores

To update a field, tell the user to use this format:
"update <field_name> to <new_value> for document <document_id>"

To validate a field (confirm extraction is correct), use:
"validate <field_name> for document <document_id>"

Be helpful, concise, and accurate in your responses.""",
            model=bedrock_model,
        )
        
        yield "💬 Analyzing your question...\n\n"
        
        # Get AI response
        response = qa_agent(user_prompt)
        response_text = str(response)
        
        yield "📋 Answer:\n\n"
        yield response_text + "\n"
    
    except Exception as e:
        import traceback
        yield f"❌ Error: {str(e)}\n"
        yield f"Traceback: {traceback.format_exc()}\n"


if __name__ == "__main__":
    app.run()
