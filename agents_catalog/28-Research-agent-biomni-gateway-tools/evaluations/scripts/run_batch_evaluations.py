#!/usr/bin/env python3
"""
Run batch evaluations on all generated test sessions.

This script:
1. Loads session information from session_info.json
2. Runs evaluations on each session with all configured evaluators
3. Saves individual results and generates a summary report

Usage:
    python scripts/run_batch_evaluations.py
    python scripts/run_batch_evaluations.py --evaluators "Builtin.Helpfulness,ResearchAgent.CitationQuality"
    python scripts/run_batch_evaluations.py --agent-id <agent_id>
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
        print("❌ No session information found!")
        print("Run generate_test_sessions.py first to generate test sessions")
        sys.exit(1)
    
    with open(session_file, 'r') as f:
        return json.load(f)


def run_evaluation(session_id, evaluators, output_file, agent_id=None):
    """
    Run AgentCore evaluation using CLI.
    
    Args:
        session_id: Session ID to evaluate
        evaluators: List of evaluator IDs
        output_file: Output file path
        agent_id: Optional agent ID
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Build command
    cmd = ["agentcore", "eval", "run", "--session-id", session_id]
    
    if agent_id:
        cmd.extend(["--agent-id", agent_id])
    
    for evaluator in evaluators:
        cmd.extend(["--evaluator", evaluator])
    
    cmd.extend(["--output", output_file])
    
    # Run evaluation
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ AgentCore CLI not found!")
        print("Please install: pip install bedrock-agentcore-starter-toolkit")
        sys.exit(1)


def parse_evaluation_results(result_file):
    """Parse evaluation results JSON and extract key metrics"""
    try:
        with open(result_file, 'r') as f:
            results = json.load(f)
        
        metrics = {}
        for result in results.get('results', []):
            evaluator_id = result.get('evaluatorId', 'unknown')
            score = result.get('score')
            label = result.get('label', '')
            
            metrics[evaluator_id] = {
                'score': score,
                'label': label
            }
        
        return metrics
    except Exception as e:
        print(f"⚠️  Warning: Could not parse results from {result_file}: {e}")
        return {}


def generate_summary_report(evaluation_results, output_file):
    """Generate summary report of all evaluations"""
    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_sessions_evaluated": len(evaluation_results),
        "successful_evaluations": sum(1 for r in evaluation_results if r['status'] == 'success'),
        "failed_evaluations": sum(1 for r in evaluation_results if r['status'] == 'failed'),
        "results": evaluation_results
    }
    
    # Calculate average scores per evaluator
    evaluator_scores = {}
    for result in evaluation_results:
        if result['status'] == 'success' and 'metrics' in result:
            for evaluator_id, metrics in result['metrics'].items():
                if evaluator_id not in evaluator_scores:
                    evaluator_scores[evaluator_id] = []
                if metrics['score'] is not None:
                    evaluator_scores[evaluator_id].append(metrics['score'])
    
    average_scores = {}
    for evaluator_id, scores in evaluator_scores.items():
        if scores:
            average_scores[evaluator_id] = {
                'average_score': sum(scores) / len(scores),
                'min_score': min(scores),
                'max_score': max(scores),
                'num_evaluations': len(scores)
            }
    
    summary['average_scores'] = average_scores
    
    # Save summary
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    return summary


def print_summary(summary):
    """Print evaluation summary to console"""
    print(f"\n{'='*80}")
    print("📊 BATCH EVALUATION SUMMARY")
    print("="*80)
    print(f"Total sessions evaluated: {summary['total_sessions_evaluated']}")
    print(f"Successful: {summary['successful_evaluations']}")
    print(f"Failed: {summary['failed_evaluations']}")
    
    if summary.get('average_scores'):
        print(f"\n{'='*80}")
        print("📈 AVERAGE SCORES BY EVALUATOR")
        print("="*80)
        
        for evaluator_id, scores in summary['average_scores'].items():
            avg = scores['average_score']
            min_s = scores['min_score']
            max_s = scores['max_score']
            count = scores['num_evaluations']
            
            print(f"\n{evaluator_id}:")
            print(f"  Average: {avg:.3f} (n={count})")
            print(f"  Range: {min_s:.3f} - {max_s:.3f}")
    
    print(f"\n{'='*80}")


def main():
    parser = argparse.ArgumentParser(description="Run batch evaluations on all test sessions")
    parser.add_argument("--agent-id", help="Agent ID (optional, uses config if not provided)")
    parser.add_argument(
        "--evaluators",
        default="Builtin.Helpfulness,Builtin.Correctness,Builtin.GoalSuccessRate,ResearchAgent.CitationQuality,ResearchAgent.ToolSelection,ResearchAgent.ResearchComprehensiveness,ResearchAgent.LiteratureSearch",
        help="Comma-separated list of evaluator IDs"
    )
    
    args = parser.parse_args()
    
    # Parse evaluators
    evaluators = [e.strip() for e in args.evaluators.split(",")]
    
    # Load session information
    print("📚 Loading session information...")
    session_data = load_session_info()
    sessions = [s for s in session_data['sessions'] if s['status'] == 'completed']
    
    if not sessions:
        print("❌ No completed sessions found!")
        print("Run generate_test_sessions.py first")
        sys.exit(1)
    
    print(f"Found {len(sessions)} completed session(s)")
    print(f"Will use {len(evaluators)} evaluator(s)")
    
    # Prepare output directory
    output_dir = Path(__file__).parent.parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Run evaluations on each session
    evaluation_results = []
    
    print(f"\n{'='*80}")
    print("🚀 Starting Batch Evaluation")
    print("="*80)
    
    for i, session in enumerate(sessions, 1):
        test_case_id = session['test_case_id']
        session_id = session['session_id']
        test_name = session['test_case_name']
        
        print(f"\n[{i}/{len(sessions)}] Evaluating: {test_case_id} - {test_name}")
        print(f"Session ID: {session_id}")
        
        # Generate output file name
        output_file = output_dir / f"eval_{test_case_id}_{timestamp}.json"
        
        # Run evaluation
        success = run_evaluation(
            session_id=session_id,
            evaluators=evaluators,
            output_file=str(output_file),
            agent_id=args.agent_id
        )
        
        result_entry = {
            "test_case_id": test_case_id,
            "test_case_name": test_name,
            "session_id": session_id,
            "status": "success" if success else "failed",
            "output_file": str(output_file) if success else None,
            "timestamp": datetime.now().isoformat()
        }
        
        # Parse and add metrics if successful
        if success:
            print(f"✅ Evaluation completed")
            metrics = parse_evaluation_results(output_file)
            result_entry['metrics'] = metrics
            
            # Print key scores
            if metrics:
                print("📊 Scores:")
                for eval_id, data in metrics.items():
                    eval_name = eval_id.split('.')[-1]
                    score = data['score']
                    label = data['label']
                    if score is not None:
                        print(f"   - {eval_name}: {score:.3f} ({label})")
        else:
            print(f"❌ Evaluation failed")
        
        evaluation_results.append(result_entry)
    
    # Generate summary report
    summary_file = output_dir / f"evaluation_summary_{timestamp}.json"
    print(f"\n📝 Generating summary report...")
    summary = generate_summary_report(evaluation_results, summary_file)
    
    # Print summary
    print_summary(summary)
    
    print(f"\n💾 Summary saved to: {summary_file}")
    print(f"💾 Individual results saved to: {output_dir}")
    
    print(f"\n{'='*80}")
    print("✅ Batch evaluation completed!")
    print("="*80)


if __name__ == "__main__":
    main()
