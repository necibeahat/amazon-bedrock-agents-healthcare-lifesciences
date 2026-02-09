#!/usr/bin/env python3
"""
Run AgentCore evaluation on a single session with specified evaluators.

This script runs evaluations using the AgentCore CLI and saves results to JSON.

Usage:
    python scripts/run_single_evaluation.py --session-id <session_id>
    python scripts/run_single_evaluation.py --session-id <session_id> --evaluators "Builtin.Helpfulness,ResearchAgent.CitationQuality"
    python scripts/run_single_evaluation.py --auto  # Use latest session from session_info.json
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime


def load_session_info():
    """Load session information from generated test sessions"""
    session_file = Path(__file__).parent.parent / "results" / "session_info.json"
    if not session_file.exists():
        return None
    
    with open(session_file, 'r') as f:
        return json.load(f)


def get_latest_session():
    """Get the most recently generated session ID"""
    session_data = load_session_info()
    if not session_data or not session_data.get('sessions'):
        return None
    
    # Get the most recent completed session
    completed_sessions = [s for s in session_data['sessions'] if s['status'] == 'completed']
    if not completed_sessions:
        return None
    
    return completed_sessions[-1]['session_id']


def run_evaluation(session_id, evaluators, output_file=None, agent_id=None):
    """
    Run AgentCore evaluation using CLI.
    
    Args:
        session_id: Session ID to evaluate
        evaluators: List of evaluator IDs
        output_file: Optional output file path
        agent_id: Optional agent ID (uses config if not provided)
    """
    print(f"\n{'='*80}")
    print(f"🎯 Running Evaluation")
    print(f"{'='*80}")
    print(f"Session ID: {session_id}")
    print(f"Evaluators: {', '.join(evaluators)}")
    print(f"{'='*80}\n")
    
    # Build agentcore eval command
    cmd = ["agentcore", "eval", "run", "--session-id", session_id]
    
    # Add agent ID if provided
    if agent_id:
        cmd.extend(["--agent-id", agent_id])
    
    # Add evaluators
    for evaluator in evaluators:
        cmd.extend(["--evaluator", evaluator])
    
    # Add output file if specified
    if output_file:
        cmd.extend(["--output", output_file])
    
    # Run the evaluation
    try:
        print("🚀 Executing evaluation...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        print(result.stdout)
        
        if output_file:
            print(f"\n✅ Results saved to: {output_file}")
            print(f"✅ Input data saved to: {output_file.replace('.json', '_input.json')}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Evaluation failed!")
        print(f"Error: {e.stderr}")
        return False
    except FileNotFoundError:
        print("\n❌ AgentCore CLI not found!")
        print("Please install: pip install bedrock-agentcore-starter-toolkit")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run evaluation on a single session")
    parser.add_argument("--session-id", help="Session ID to evaluate")
    parser.add_argument("--auto", action="store_true", help="Use latest session from session_info.json")
    parser.add_argument("--agent-id", help="Agent ID (optional, uses config if not provided)")
    parser.add_argument(
        "--evaluators",
        default="Builtin.Helpfulness,Builtin.Correctness,Builtin.GoalSuccessRate,ResearchAgent.CitationQuality,ResearchAgent.ToolSelection,ResearchAgent.ResearchComprehensiveness,ResearchAgent.LiteratureSearch",
        help="Comma-separated list of evaluator IDs"
    )
    parser.add_argument(
        "--output",
        help="Output file path (optional, generates from session ID if not provided)"
    )
    
    args = parser.parse_args()
    
    # Determine session ID
    session_id = args.session_id
    if args.auto:
        session_id = get_latest_session()
        if not session_id:
            print("❌ No completed sessions found in session_info.json")
            print("Run generate_test_sessions.py first")
            sys.exit(1)
        print(f"📋 Using latest session: {session_id}")
    
    if not session_id:
        print("❌ No session ID provided. Use --session-id or --auto")
        sys.exit(1)
    
    # Parse evaluators
    evaluators = [e.strip() for e in args.evaluators.split(",")]
    
    # Generate output file name if not provided
    output_file = args.output
    if not output_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(__file__).parent.parent / "results"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = str(output_dir / f"eval_{session_id[:8]}_{timestamp}.json")
    
    # Run evaluation
    success = run_evaluation(
        session_id=session_id,
        evaluators=evaluators,
        output_file=output_file,
        agent_id=args.agent_id
    )
    
    if success:
        print("\n✅ Evaluation completed successfully!")
    else:
        print("\n❌ Evaluation failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
