#!/usr/bin/env python3
"""
Test script for the Quality Check Agent
This script tests the quality check agent's ability to query and validate data in DynamoDB
"""

import asyncio
import os
import sys
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

# Add the agent directory to the path
agent_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'agent')
sys.path.insert(0, agent_dir)

# Configuration (must match quality_check_agent.py)
DYNAMODB_TABLE_NAME = "IDP_Agent"

async def test_quality_check_agent():
    """Test the quality check agent with various queries"""
    
    print("="*70)
    print("🔍 QUALITY CHECK AGENT TEST")
    print("="*70)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Import the quality check agent
    try:
        from quality_check_agent import quality_check_agent
        print("✅ Successfully imported quality_check_agent")
    except ImportError as e:
        print(f"❌ Failed to import quality_check_agent: {e}")
        print(f"   Agent directory: {agent_dir}")
        return
    
    # Initialize AWS clients
    try:
        dynamodb_client = boto3.client('dynamodb')
        # Verify AWS credentials
        identity = boto3.client('sts').get_caller_identity()
        print("✅ AWS credentials configured")
        print(f"   Account: {identity['Account']}")
        print(f"   User/Role: {identity['Arn'].split('/')[-1]}")
    except Exception as e:
        print(f"❌ AWS credentials error: {e}")
        print("   Please configure AWS credentials before running the test.")
        return
    
    # Display configuration
    print("\n📋 Configuration:")
    print(f"  AWS Region: {os.environ.get('AWS_REGION', boto3.Session().region_name)}")
    print(f"  DynamoDB Table: {DYNAMODB_TABLE_NAME}")
    print()
    
    # Check if DynamoDB table exists and has data
    print("🔍 Verifying prerequisites...")
    try:
        # First check if table exists
        dynamodb_client.describe_table(TableName=DYNAMODB_TABLE_NAME)
        
        # Get actual item count using scan (ItemCount from describe_table can be outdated)
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        response = table.scan(Select='COUNT', Limit=1)
        actual_count = response.get('Count', 0)
        
        # If no items in first page, check if there are more
        if actual_count == 0:
            response = table.scan(Limit=1)
            actual_count = len(response.get('Items', []))
        
        if actual_count == 0:
            print(f"❌ DynamoDB table '{DYNAMODB_TABLE_NAME}' exists but is empty")
            print("\n💡 Please run the database agent test first:")
            print("   python test_database_agent.py")
            return
        
        print(f"✅ DynamoDB table '{DYNAMODB_TABLE_NAME}' found")
        print(f"   Items in table: {actual_count}+ (verified by scan)")
        print()
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"❌ DynamoDB table '{DYNAMODB_TABLE_NAME}' does not exist")
            print("\n💡 Please run the database agent test first:")
            print("   python test_database_agent.py")
        else:
            print(f"❌ Error accessing DynamoDB: {str(e)}")
        return
    except Exception as e:
        print(f"❌ Error checking prerequisites: {str(e)}")
        return
    
    # Get a sample document ID from the table
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        response = table.scan(Limit=1)
        sample_doc = response.get('Items', [])[0] if response.get('Items') else None
        sample_doc_id = sample_doc.get('document_id') if sample_doc else None
        
        if sample_doc:
            print(f"📄 Sample document found:")
            print(f"   Document ID: {sample_doc_id}")
            print(f"   Source: {sample_doc.get('source_file', 'N/A')}")
            
            # Get first field name for testing
            extracted_fields = sample_doc.get('extracted_fields', {})
            sample_field = list(extracted_fields.keys())[0] if extracted_fields else None
            
            if sample_field:
                field_info = extracted_fields[sample_field]
                field_value = field_info.get('value') if isinstance(field_info, dict) else field_info
                field_confidence = field_info.get('confidence', 'N/A') if isinstance(field_info, dict) else 'N/A'
                print(f"   Sample field: {sample_field}")
                print(f"   Value: {field_value}")
                print(f"   Confidence: {field_confidence}")
            print()
    except Exception as e:
        print(f"⚠️  Could not get sample document: {str(e)}\n")
        sample_doc_id = None
        sample_field = None
    
    # Define test queries
    test_queries = [
        {
            "name": "General Query - List All Patients",
            "prompt": "What patients are in the database? List all the patient names and IDs.",
            "description": "Tests basic data retrieval and summarization"
        },
        {
            "name": "Specific Query - Patient Details",
            "prompt": "Tell me about the first patient's information. What are their contact details and medical information?",
            "description": "Tests detailed data extraction for a specific patient"
        },
        {
            "name": "Confidence Analysis",
            "prompt": "Which fields have low confidence scores (below 0.8)? List them with their confidence values.",
            "description": "Tests ability to identify fields needing validation"
        },
        {
            "name": "Field Statistics",
            "prompt": "How many fields have been validated vs not validated? Give me a summary.",
            "description": "Tests data analysis capabilities"
        }
    ]
    
    # Add validation test if we have sample data
    if sample_doc_id and sample_field:
        test_queries.append({
            "name": "Validation Test",
            "prompt": f"validate {sample_field} for document {sample_doc_id}",
            "description": "Tests field validation functionality"
        })
    
    # Run each test query
    for idx, test_query in enumerate(test_queries, 1):
        print("="*70)
        print(f"TEST {idx}/{len(test_queries)}: {test_query['name']}")
        print("="*70)
        print(f"Description: {test_query['description']}")
        print(f"Query: {test_query['prompt']}")
        print()
        
        payload = {
            "prompt": test_query['prompt'],
            "sessionId": f"test-session-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{idx}"
        }
        
        print("-"*70)
        print("🤖 Agent Response:")
        print("-"*70)
        print()
        
        try:
            # Call the quality check agent and stream output
            async for chunk in quality_check_agent(payload):
                print(chunk, end='', flush=True)
            
            print()
            print("-"*70)
            print(f"✅ Test {idx} completed")
            print("-"*70)
            print()
            
            # Wait a moment between tests
            await asyncio.sleep(1)
            
        except Exception as e:
            print()
            print("-"*70)
            print(f"❌ Test {idx} failed with error:")
            print(f"   {type(e).__name__}: {str(e)}")
            print("-"*70)
            import traceback
            traceback.print_exc()
            print()
    
    print("="*70)
    print("✅ ALL TESTS COMPLETED")
    print("="*70)
    print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Show usage examples
    print("💡 Manual Testing Examples:")
    print()
    print("   1. Ask about specific patient data:")
    print("      \"What is John Smith's phone number?\"")
    print()
    print("   2. Query by field:")
    print("      \"Show me all emergency contact information\"")
    print()
    print("   3. Validate a field:")
    print(f"      \"validate {sample_field if sample_field else 'patient_name'} for document {sample_doc_id if sample_doc_id else 'doc123'}\"")
    print()
    print("   4. Update a field:")
    print(f"      \"update {sample_field if sample_field else 'phone'} to 555-1234 for document {sample_doc_id if sample_doc_id else 'doc123'}\"")
    print()
    print("   5. Check validation status:")
    print("      \"Which fields still need validation?\"")
    print()


async def interactive_mode():
    """Run the quality check agent in interactive mode"""
    print("="*70)
    print("💬 INTERACTIVE QUALITY CHECK AGENT")
    print("="*70)
    print()
    print("Ask questions about the extracted data, or use commands:")
    print("  - Ask questions: 'What patients are in the database?'")
    print("  - Validate field: 'validate phone for document doc123'")
    print("  - Update field: 'update phone to 555-1234 for document doc123'")
    print("  - Type 'quit' or 'exit' to stop")
    print()
    
    # Import the quality check agent
    try:
        from quality_check_agent import quality_check_agent
    except ImportError as e:
        print(f"❌ Failed to import quality_check_agent: {e}")
        return
    
    # Check prerequisites
    try:
        dynamodb_client = boto3.client('dynamodb')
        # First check if table exists
        dynamodb_client.describe_table(TableName=DYNAMODB_TABLE_NAME)
        
        # Get actual item count using scan (ItemCount from describe_table can be outdated)
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        response = table.scan(Select='COUNT', Limit=1)
        actual_count = response.get('Count', 0)
        
        # If no items in first page, check if there are more
        if actual_count == 0:
            response = table.scan(Limit=1)
            actual_count = len(response.get('Items', []))
        
        if actual_count == 0:
            print(f"❌ DynamoDB table '{DYNAMODB_TABLE_NAME}' is empty")
            print("   Please run the database agent test first")
            return
        
        print(f"✅ Connected to DynamoDB table with {actual_count}+ items\n")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"❌ DynamoDB table '{DYNAMODB_TABLE_NAME}' does not exist")
            print("   Please run the database agent test first")
        else:
            print(f"❌ Error: {str(e)}")
        return
    
    session_counter = 0
    
    while True:
        try:
            print("-"*70)
            user_input = input("Your query: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break
            
            print()
            
            session_counter += 1
            payload = {
                "prompt": user_input,
                "sessionId": f"interactive-session-{session_counter}"
            }
            
            # Call the quality check agent and stream output
            async for chunk in quality_check_agent(payload):
                print(chunk, end='', flush=True)
            
            print("\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}\n")


def main():
    """Main entry point for the test script"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Test the Quality Check Agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Run automated test suite
  python test_quality_check_agent.py
  
  # Run in interactive mode
  python test_quality_check_agent.py --interactive
  
  # Set environment variables before running
  export AWS_REGION=us-east-1
  python test_quality_check_agent.py

Notes:
  - This test requires data in DynamoDB from the database agent
  - Run test_database_agent.py first if you haven't already
  - AWS credentials must be configured
  - The agent can answer questions, validate fields, and update values
        '''
    )
    
    parser.add_argument(
        '--interactive',
        '-i',
        action='store_true',
        help='Run in interactive mode for manual testing'
    )
    
    args = parser.parse_args()
    
    if args.interactive:
        asyncio.run(interactive_mode())
    else:
        # Run automated test suite
        asyncio.run(test_quality_check_agent())


if __name__ == "__main__":
    main()
