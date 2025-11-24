#!/usr/bin/env python3
"""
Test script for the Database Agent
This script invokes the database agent to load extracted data from S3 into DynamoDB
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

# Configuration (must match database_agent.py)
INPUT_BUCKET = "idp-wwso-output"
INPUT_PREFIX = "extracted-data/"
DYNAMODB_TABLE_NAME = "IDP_Agent"

async def test_database_agent():
    """Test the database agent with extracted data from S3"""
    
    print("="*70)
    print("💾 DATABASE AGENT TEST")
    print("="*70)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Import the database agent
    try:
        from database_agent import database_agent
        print("✅ Successfully imported database_agent")
    except ImportError as e:
        print(f"❌ Failed to import database_agent: {e}")
        print(f"   Agent directory: {agent_dir}")
        return
    
    # Initialize AWS clients
    try:
        s3_client = boto3.client('s3')
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
    print(f"  Input Bucket: {INPUT_BUCKET}")
    print(f"  Input Prefix: {INPUT_PREFIX}")
    print(f"  DynamoDB Table: {DYNAMODB_TABLE_NAME}")
    print()
    
    # Check if extracted data exists in S3
    print("🔍 Verifying prerequisites...")
    try:
        response = s3_client.list_objects_v2(
            Bucket=INPUT_BUCKET,
            Prefix=INPUT_PREFIX
        )
        
        if 'Contents' not in response:
            print(f"❌ No files found in s3://{INPUT_BUCKET}/{INPUT_PREFIX}")
            print("\n💡 Please run the extractor agent test first:")
            print("   python test_extractor_agent.py")
            return
        
        json_files = [obj['Key'] for obj in response['Contents'] 
                     if obj['Key'].lower().endswith('.json')]
        
        if not json_files:
            print(f"❌ No JSON files found in s3://{INPUT_BUCKET}/{INPUT_PREFIX}")
            print("\n💡 Please run the extractor agent test first:")
            print("   python test_extractor_agent.py")
            return
        
        print(f"✅ Found {len(json_files)} JSON file(s) ready for processing")
        print("\n📄 Files to import:")
        for idx, key in enumerate(json_files[:5], 1):  # Show first 5
            print(f"   {idx}. {os.path.basename(key)}")
        if len(json_files) > 5:
            print(f"   ... and {len(json_files) - 5} more")
        print()
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucket':
            print(f"❌ Bucket '{INPUT_BUCKET}' does not exist")
            print("\n💡 Please run the extractor agent test first:")
            print("   python test_extractor_agent.py")
        else:
            print(f"❌ Error accessing S3: {str(e)}")
        return
    except Exception as e:
        print(f"❌ Error checking prerequisites: {str(e)}")
        return
    
    # Check current DynamoDB table state
    try:
        table_desc = dynamodb_client.describe_table(TableName=DYNAMODB_TABLE_NAME)
        item_count = table_desc['Table']['ItemCount']
        print(f"📊 Current DynamoDB state:")
        print(f"   Table: {DYNAMODB_TABLE_NAME}")
        print(f"   Current items: {item_count}")
        print()
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"ℹ️  DynamoDB table '{DYNAMODB_TABLE_NAME}' doesn't exist yet")
            print("   (It will be created automatically)\n")
        else:
            print(f"⚠️  Could not check table status: {str(e)}\n")
    
    # Create test payload
    payload = {
        "prompt": "Import all extracted data from S3 into DynamoDB",
        "sessionId": f"test-session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    }
    
    print("📦 Test Payload:")
    print(f"  Prompt: {payload['prompt']}")
    print(f"  Session ID: {payload['sessionId']}")
    print()
    
    print("-"*70)
    print("🚀 Starting Database Agent...")
    print("-"*70)
    print()
    
    try:
        # Call the database agent and stream output
        async for chunk in database_agent(payload):
            print(chunk, end='', flush=True)
        
        print()
        print("-"*70)
        print("✅ Test completed successfully!")
        print("-"*70)
        
        # Show updated table state
        try:
            table_desc = dynamodb_client.describe_table(TableName=DYNAMODB_TABLE_NAME)
            item_count = table_desc['Table']['ItemCount']
            print(f"\n📊 Final DynamoDB state:")
            print(f"   Table: {DYNAMODB_TABLE_NAME}")
            print(f"   Total items: {item_count}")
            print()
        except Exception:
            pass
        
    except Exception as e:
        print()
        print("-"*70)
        print(f"❌ Test failed with error:")
        print(f"   {type(e).__name__}: {str(e)}")
        print("-"*70)
        import traceback
        traceback.print_exc()
    
    print(f"\nEnd Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Show query examples
    print("\n💡 Next steps:")
    print("   1. Query DynamoDB table:")
    print(f"      aws dynamodb scan --table-name {DYNAMODB_TABLE_NAME} --max-items 5")
    print()
    print("   2. Run the quality check agent to validate and update data:")
    print("      python test_quality_check_agent.py")
    print()
    print("   3. View items in AWS Console:")
    print("      https://console.aws.amazon.com/dynamodb/home")


async def show_table_contents():
    """Display contents of the DynamoDB table"""
    print("="*70)
    print("📊 DYNAMODB TABLE CONTENTS")
    print("="*70)
    print()
    
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        
        print(f"Scanning table: {DYNAMODB_TABLE_NAME}\n")
        
        response = table.scan(Limit=10)
        items = response.get('Items', [])
        
        if not items:
            print("❌ No items found in table")
            return
        
        print(f"✅ Found {len(items)} items (showing up to 10):\n")
        
        for idx, item in enumerate(items, 1):
            print(f"{idx}. Document ID: {item.get('document_id', 'N/A')}")
            print(f"   Source: {item.get('source_file', 'N/A')}")
            print(f"   Extraction Time: {item.get('extraction_timestamp', 'N/A')}")
            print(f"   Import Time: {item.get('database_import_timestamp', 'N/A')}")
            
            extracted_fields = item.get('extracted_fields', {})
            print(f"   Fields: {len(extracted_fields)}")
            
            # Show first 3 fields
            field_count = 0
            for field_name, field_data in extracted_fields.items():
                if field_count < 3:
                    value = field_data.get('value', 'N/A') if isinstance(field_data, dict) else field_data
                    confidence = field_data.get('confidence', 'N/A') if isinstance(field_data, dict) else 'N/A'
                    validated = field_data.get('validated', False) if isinstance(field_data, dict) else False
                    print(f"     - {field_name}: {value} (confidence: {confidence}, validated: {validated})")
                    field_count += 1
            
            if len(extracted_fields) > 3:
                print(f"     ... and {len(extracted_fields) - 3} more fields")
            print()
        
        if response.get('LastEvaluatedKey'):
            print(f"⚠️  More items available (table contains more than 10 items)")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"❌ Table '{DYNAMODB_TABLE_NAME}' does not exist")
            print("\n💡 Run the database agent test first:")
            print("   python test_database_agent.py")
        else:
            print(f"❌ Error: {str(e)}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point for the test script"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Test the Database Agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Run the database agent test
  python test_database_agent.py
  
  # Show current DynamoDB table contents
  python test_database_agent.py --show-contents
  
  # Set environment variables before running
  export AWS_REGION=us-east-1
  python test_database_agent.py

Notes:
  - This test requires extracted JSON files in S3 from the extractor agent
  - Run test_extractor_agent.py first if you haven't already
  - The DynamoDB table will be created automatically if it doesn't exist
  - AWS credentials must be configured
        '''
    )
    
    parser.add_argument(
        '--show-contents',
        action='store_true',
        help='Display current DynamoDB table contents'
    )
    
    args = parser.parse_args()
    
    if args.show_contents:
        asyncio.run(show_table_contents())
    else:
        # Run the test
        asyncio.run(test_database_agent())


if __name__ == "__main__":
    main()
