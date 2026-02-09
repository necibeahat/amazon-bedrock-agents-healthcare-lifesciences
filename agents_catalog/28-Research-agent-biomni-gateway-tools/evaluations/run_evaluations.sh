#!/bin/bash
# Main evaluation runner script for Research Agent
# This script orchestrates the complete evaluation workflow

set -e  # Exit on any error

echo "================================================================================"
echo "🧪 Research Agent Evaluation Suite"
echo "================================================================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Parse command line arguments
SKIP_SESSION_GEN=false
SKIP_WAIT=false
TEST_CASE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-session-gen)
            SKIP_SESSION_GEN=true
            shift
            ;;
        --skip-wait)
            SKIP_WAIT=true
            shift
            ;;
        --test-case)
            TEST_CASE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: ./run_evaluations.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-session-gen    Skip test session generation (use existing sessions)"
            echo "  --skip-wait          Skip CloudWatch propagation wait"
            echo "  --test-case <id>     Run only a specific test case (e.g., tc_001)"
            echo "  --help               Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./run_evaluations.sh                           # Full evaluation run"
            echo "  ./run_evaluations.sh --test-case tc_001        # Run only test case tc_001"
            echo "  ./run_evaluations.sh --skip-session-gen        # Use existing sessions"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Step 1: Generate test sessions (unless skipped)
if [ "$SKIP_SESSION_GEN" = false ]; then
    echo "📝 Step 1: Generating Test Sessions"
    echo "================================================================================"
    echo ""
    
    GEN_CMD="python $SCRIPT_DIR/scripts/generate_test_sessions.py"
    
    if [ -n "$TEST_CASE" ]; then
        GEN_CMD="$GEN_CMD --test-case $TEST_CASE"
    fi
    
    if [ "$SKIP_WAIT" = true ]; then
        GEN_CMD="$GEN_CMD --skip-wait"
    fi
    
    if $GEN_CMD; then
        echo ""
        echo "✅ Test sessions generated successfully"
    else
        echo ""
        echo "❌ Failed to generate test sessions"
        exit 1
    fi
else
    echo "⏭️  Skipping test session generation (using existing sessions)"
fi

# Step 2: Wait for CloudWatch propagation if needed and not skipped
if [ "$SKIP_SESSION_GEN" = false ] && [ "$SKIP_WAIT" = true ]; then
    echo ""
    echo "================================================================================"
    echo "⏳ CloudWatch Propagation Wait"
    echo "================================================================================"
    echo ""
    echo "⚠️  You chose to skip the automatic wait."
    echo "Please ensure CloudWatch logs have propagated (typically 2-5 minutes)"
    echo "before the evaluation will find session data."
    echo ""
    read -p "Press Enter to continue when ready, or Ctrl+C to cancel..."
fi

# Step 3: Run batch evaluations
echo ""
echo "================================================================================"
echo "📊 Step 2: Running Batch Evaluations"
echo "================================================================================"
echo ""

if python "$SCRIPT_DIR/scripts/run_batch_evaluations.py"; then
    echo ""
    echo "✅ Batch evaluations completed successfully"
else
    echo ""
    echo "❌ Batch evaluations failed"
    exit 1
fi

# Step 4: Display results summary
echo ""
echo "================================================================================"
echo "🎉 Evaluation Complete!"
echo "================================================================================"
echo ""
echo "📁 Results Location: $SCRIPT_DIR/results/"
echo ""
echo "Files generated:"
echo "  • session_info.json           - Test session information"
echo "  • eval_*_*.json               - Individual evaluation results"
echo "  • evaluation_summary_*.json   - Comprehensive summary report"
echo ""
echo "Next steps:"
echo "  1. Review evaluation_summary_*.json for overall metrics"
echo "  2. Check individual eval_*.json files for detailed results"
echo "  3. View CloudWatch for detailed trace information"
echo ""
echo "To re-run evaluations on existing sessions:"
echo "  ./run_evaluations.sh --skip-session-gen"
echo ""
echo "================================================================================"
