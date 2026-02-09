#!/bin/bash
# Setup script to create all custom evaluators for Research Agent evaluation
# This script must be run once before running evaluations

set -e  # Exit on any error

echo "================================================================================"
echo "🚀 Setting Up Custom Evaluators for Research Agent"
echo "================================================================================"
echo ""

# Check if AgentCore CLI is installed
if ! command -v agentcore &> /dev/null; then
    echo "❌ Error: AgentCore CLI not found!"
    echo ""
    echo "Please install the Amazon Bedrock AgentCore starter toolkit:"
    echo "  pip install bedrock-agentcore-starter-toolkit"
    echo ""
    exit 1
fi

echo "✓ AgentCore CLI found"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
EVALUATORS_DIR="$SCRIPT_DIR/../evaluators"

echo "Evaluators directory: $EVALUATORS_DIR"
echo ""

# Function to create an evaluator
create_evaluator() {
    local name=$1
    local config_file=$2
    local level=$3
    local description=$4
    
    echo "--------------------------------------------------------------------------------"
    echo "Creating evaluator: $name"
    echo "Config file: $config_file"
    echo "Level: $level"
    echo "--------------------------------------------------------------------------------"
    
    if agentcore eval evaluator create \
        --name "$name" \
        --config "$config_file" \
        --level "$level" \
        --description "$description"; then
        echo "✅ Successfully created: $name"
    else
        echo "⚠️  Warning: Failed to create $name (it may already exist)"
    fi
    echo ""
}

# Create Citation Quality Evaluator
create_evaluator \
    "ResearchAgent.CitationQuality" \
    "$EVALUATORS_DIR/citation_quality.json" \
    "TRACE" \
    "Evaluates citation formatting and reference accuracy in biomedical research responses"

# Create Tool Selection Evaluator
create_evaluator \
    "ResearchAgent.ToolSelection" \
    "$EVALUATORS_DIR/tool_selection.json" \
    "TOOL_CALL" \
    "Evaluates appropriate selection of Biomni database tools and PubMed for research queries"

# Create Research Comprehensiveness Evaluator
create_evaluator \
    "ResearchAgent.ResearchComprehensiveness" \
    "$EVALUATORS_DIR/research_comprehensiveness.json" \
    "SESSION" \
    "Evaluates completeness and depth of research coverage across multiple databases"

# Create Literature Search Effectiveness Evaluator
create_evaluator \
    "ResearchAgent.LiteratureSearch" \
    "$EVALUATORS_DIR/literature_search.json" \
    "TOOL_CALL" \
    "Evaluates quality and appropriateness of PubMed search strategies"

echo "================================================================================"
echo "📋 Listing All Evaluators"
echo "================================================================================"
echo ""

agentcore eval evaluator list

echo ""
echo "================================================================================"
echo "✅ Custom Evaluator Setup Complete!"
echo "================================================================================"
echo ""
echo "Custom evaluators created:"
echo "  ✓ ResearchAgent.CitationQuality"
echo "  ✓ ResearchAgent.ToolSelection"
echo "  ✓ ResearchAgent.ResearchComprehensiveness"
echo "  ✓ ResearchAgent.LiteratureSearch"
echo ""
echo "Built-in evaluators available:"
echo "  ✓ Builtin.Helpfulness"
echo "  ✓ Builtin.Correctness"
echo "  ✓ Builtin.GoalSuccessRate"
echo "  ✓ Builtin.Faithfulness"
echo "  ... and more"
echo ""
echo "Next steps:"
echo "  1. Generate test sessions: python scripts/generate_test_sessions.py"
echo "  2. Run evaluations: ./run_evaluations.sh"
echo ""
echo "================================================================================"
