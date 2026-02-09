#!/usr/bin/env python3
"""
Generate test sessions by invoking the Research Agent with test queries.

This script:
1. Loads test queries from test_queries.json
2. Invokes the agent with each query using the deployed AgentCore runtime
3. Waits for CloudWatch log propagation (2-5 minutes per session)
4. Saves session IDs to a file for later evaluation

Usage:
    python scripts/generate_test_sessions.py
    python scripts/generate_test_sessions.py --test-case tc_001  # Run specific test case
    python scripts/generate_test_sessions.py --skip-wait  # Don't wait for CloudWatch
"""

import asyncio
import json
import sys
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.agent_config.agent import agent_task


def load_test_queries():
    """Load test queries from test_queries.json"""
    test_file = Path(__file__).parent.parent / "test_queries.json"
    with open(test_file, 'r') as f:
        return json.load(f)


async def invoke_agent(test_case):
    """
    Invoke the agent with a test query and return session information.
    
    Args:
        test_case: Test case dictionary from test_queries.json
        
    Returns:
        dict: Session information including session_id, test_case_id, timestamp
    """
    import uuid
    
    test_id = test_case['id']
    query = test_case['query']
    
    # Generate unique session ID
    session_id = str(uuid.uuid4())
    actor_id = f"evaluation_test_{test_id}"
    
    print(f"\n{'='*80}")
    print(f"🧪 Running Test Case: {test_id}")
    print(f"📝 Name: {test_case['name']}")
    print(f"🔗 Session ID: {session_id}")
    print(f"{'='*80}\n")
    
    # Invoke agent and stream response
    full_response = ""
    try:
        async for chunk in agent_task(
            user_message=query,
            session_id=session_id,
            actor_id=actor_id,
            use_semantic_search=False  # Use all tools for comprehensive testing
        ):
            print(chunk, end="", flush=True)
            full_response += chunk
            
        print("\n")
        
        return {
            "test_case_id": test_id,
            "test_case_name": test_case['name'],
            "session_id": session_id,
            "actor_id": actor_id,
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "status": "completed",
            "response_length": len(full_response)
        }
        
    except Exception as e:
        print(f"\n❌ Error invoking agent: {str(e)}\n")
        return {
            "test_case_id": test_id,
            "test_case_name": test_case['name'],
            "session_id": session_id,
            "actor_id": actor_id,
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "status": "failed",
            "error": str(e)
        }


def save_session_info(sessions, output_file):
    """Save session information to JSON file"""
    with open(output_file, 'w') as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "total_sessions": len(sessions),
            "sessions": sessions
        }, f, indent=2)
    
    print(f"\n✅ Session information saved to: {output_file}")


async def main():
    parser = argparse.ArgumentParser(description="Generate test sessions for Research Agent evaluation")
    parser.add_argument("--test-case", help="Run specific test case (e.g., tc_001)")
    parser.add_argument("--skip-wait", action="store_true", help="Skip waiting for CloudWatch propagation")
    parser.add_argument("--output", default="evaluations/results/session_info.json", help="Output file for session information")
    
    args = parser.parse_args()
    
    # Load test queries
    print("📚 Loading test queries...")
    test_data = load_test_queries()
    test_cases = test_data['test_cases']
    
    # Filter to specific test case if requested
    if args.test_case:
        test_cases = [tc for tc in test_cases if tc['id'] == args.test_case]
        if not test_cases:
            print(f"❌ Test case {args.test_case} not found")
            return
    
    print(f"🎯 Will run {len(test_cases)} test case(s)")
    
    # Run test cases
    sessions = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'#'*80}")
        print(f"# Test {i}/{len(test_cases)}")
        print(f"{'#'*80}")
        
        session_info = await invoke_agent(test_case)
        sessions.append(session_info)
        
        # Wait between test cases (except for the last one)
        if i < len(test_cases):
            print(f"\n⏸️  Waiting 10 seconds before next test case...\n")
            time.sleep(10)
    
    # Save session information
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_session_info(sessions, output_path)
    
    # Wait for CloudWatch propagation
    if not args.skip_wait:
        print(f"\n{'='*80}")
        print("⏳ IMPORTANT: Waiting for CloudWatch Log Propagation")
        print("="*80)
        print("\nCloudWatch logs typically take 2-5 minutes to propagate.")
        print("This wait is necessary for the evaluation to find session data.")
        print(f"\nWaiting 5 minutes (300 seconds)...\n")
        
        for remaining in range(300, 0, -30):
            print(f"⏱️  {remaining} seconds remaining...")
            time.sleep(30)
        
        print("\n✅ CloudWatch propagation wait complete!")
    else:
        print("\n⚠️  Skipped CloudWatch wait. You may need to wait manually before running evaluations.")
    
    # Print summary
    print(f"\n{'='*80}")
    print("📊 SESSION GENERATION SUMMARY")
    print("="*80)
    print(f"Total sessions generated: {len(sessions)}")
    print(f"Successful: {sum(1 for s in sessions if s['status'] == 'completed')}")
    print(f"Failed: {sum(1 for s in sessions if s['status'] == 'failed')}")
    
    print("\n📋 Session IDs:")
    for session in sessions:
        status_icon = "✅" if session['status'] == 'completed' else "❌"
        print(f"  {status_icon} {session['test_case_id']}: {session['session_id']}")
    
    print(f"\n💾 Session info saved to: {args.output}")
    print("\n🎯 Next steps:")
    print("   1. Run evaluations with: python scripts/run_batch_evaluations.py")
    print("   2. Or run single evaluation: python scripts/run_single_evaluation.py --session-id <id>")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
