#!/usr/bin/env python3
"""
Test script for the Extractor Agent
This script uploads a PDF from the local /data folder to S3 and invokes the extractor agent
"""

import asyncio
import os
import sys
from datetime import datetime
import boto3
from pathlib import Path

# Add the agent directory to the path
agent_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'agent')
sys.path.insert(0, agent_dir)

# S3 Configuration (must match extractor_agent.py)
INPUT_BUCKET = "idp-wwso-input-files"
INPUT_PREFIX = "input-pdfs/"
OUTPUT_BUCKET = "idp-wwso-output"

async def test_extractor_agent():
    """Test the extractor agent with real data from /data folder"""
    
    print("="*70)
    print("🧪 EXTRACTOR AGENT TEST")
    print("="*70)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Import the extractor agent
    try:
        from extractor_agent import extractor_agent
        print("✅ Successfully imported extractor_agent")
    except ImportError as e:
        print(f"❌ Failed to import extractor_agent: {e}")
        print(f"   Agent directory: {agent_dir}")
        return
    
    # Initialize S3 client
    try:
        s3_client = boto3.client('s3')
        # Verify AWS credentials
        boto3.client('sts').get_caller_identity()
        print("✅ AWS credentials configured")
    except Exception as e:
        print(f"❌ AWS credentials error: {e}")
        print("   Please configure AWS credentials before running the test.")
        return
    
    # Display environment configuration
    print("\n📋 Configuration:")
    print(f"  AWS Region: {os.environ.get('AWS_REGION', 'us-east-1')}")
    print(f"  BDA Project ARN: {os.environ.get('BDA_PROJECT_ARN', 'default')}")
    print(f"  Input Bucket: {INPUT_BUCKET}")
    print(f"  Output Bucket: {OUTPUT_BUCKET}")
    print()
    
    # Locate the test PDF file in /data folder
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    test_pdf = os.path.join(data_dir, 'Sample_Filled_MedicalIntakeForm.pdf')
    
    if not os.path.exists(test_pdf):
        print(f"❌ Test PDF file not found: {test_pdf}")
        return
    
    print(f"📄 Found test PDF: {test_pdf}")
    print(f"   File size: {os.path.getsize(test_pdf)} bytes")
    print()
    
    # Ensure S3 buckets exist
    print("🔧 Verifying S3 buckets...")
    try:
        # Check/create input bucket
        try:
            s3_client.head_bucket(Bucket=INPUT_BUCKET)
            print(f"✅ Input bucket exists: {INPUT_BUCKET}")
        except:
            print(f"⚠️  Input bucket doesn't exist, creating: {INPUT_BUCKET}")
            s3_client.create_bucket(Bucket=INPUT_BUCKET)
            print(f"✅ Created input bucket: {INPUT_BUCKET}")
        
        # Check/create output bucket
        try:
            s3_client.head_bucket(Bucket=OUTPUT_BUCKET)
            print(f"✅ Output bucket exists: {OUTPUT_BUCKET}")
        except:
            print(f"⚠️  Output bucket doesn't exist, creating: {OUTPUT_BUCKET}")
            s3_client.create_bucket(Bucket=OUTPUT_BUCKET)
            print(f"✅ Created output bucket: {OUTPUT_BUCKET}")
    except Exception as e:
        print(f"❌ Error with S3 buckets: {e}")
        return
    
    print()
    
    # Upload test PDF to S3
    s3_key = f"{INPUT_PREFIX}{os.path.basename(test_pdf)}"
    print(f"⬆️  Uploading test PDF to S3...")
    print(f"   Destination: s3://{INPUT_BUCKET}/{s3_key}")
    
    try:
        s3_client.upload_file(test_pdf, INPUT_BUCKET, s3_key)
        print("✅ Upload successful")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return
    
    print()
    
    # Create test payload
    payload = {
        "prompt": "Process all PDF documents in the input bucket",
        "sessionId": f"test-session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    }
    
    print("📦 Test Payload:")
    print(f"  Prompt: {payload['prompt']}")
    print(f"  Session ID: {payload['sessionId']}")
    print()
    
    print("-"*70)
    print("🚀 Starting Extractor Agent...")
    print("-"*70)
    print()
    
    try:
        # Call the extractor agent and stream output
        async for chunk in extractor_agent(payload):
            print(chunk, end='', flush=True)
        
        print()
        print("-"*70)
        print("✅ Test completed successfully!")
        print("-"*70)
        
    except Exception as e:
        print()
        print("-"*70)
        print(f"❌ Test failed with error:")
        print(f"   {type(e).__name__}: {str(e)}")
        print("-"*70)
        import traceback
        traceback.print_exc()
    
    print(f"\nEnd Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Cleanup option
    print("\n💡 Tip: To clean up test data from S3, run:")
    print(f"   aws s3 rm s3://{INPUT_BUCKET}/{s3_key}")
    print(f"   aws s3 rm s3://{OUTPUT_BUCKET}/extracted-data/ --recursive")


def main():
    """Main entry point for the test script"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Test the Extractor Agent with real data from /data folder',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Run the extractor agent test
  python test_extractor_agent.py
  
  # Set environment variables before running
  export AWS_REGION=us-east-1
  export BDA_PROJECT_ARN=arn:aws:bedrock:us-east-1:774305571746:data-automation-project/ef41d092d129
  python test_extractor_agent.py

Notes:
  - This test uses the Sample_Filled_MedicalIntakeForm.pdf from the /data folder
  - The test uploads the PDF to S3 and calls the extractor_agent to process it
  - AWS credentials must be configured
  - Required S3 buckets will be created if they don't exist
        '''
    )
    
    args = parser.parse_args()
    
    # Run the test
    asyncio.run(test_extractor_agent())


if __name__ == "__main__":
    main()
