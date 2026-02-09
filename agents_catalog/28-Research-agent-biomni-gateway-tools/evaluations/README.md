# Research Agent Evaluation Framework

Comprehensive evaluation framework for the Biomedical Research Agent using Amazon Bedrock AgentCore native evaluation capabilities.

## Overview

This evaluation framework provides systematic assessment of the Research Agent's performance across multiple dimensions:

- **Response Quality**: Helpfulness, correctness, and goal achievement
- **Tool Selection**: Appropriate use of Biomni database tools and PubMed
- **Literature Search**: Quality of PubMed search strategies
- **Citation Quality**: Proper citation formatting and reference accuracy
- **Research Comprehensiveness**: Completeness of research coverage
- **Overall Performance**: Aggregated metrics and insights

## Architecture

### Directory Structure

```
evaluations/
├── README.md                          # This file
├── test_queries.json                  # Test cases from sample queries
├── setup_evaluators.sh                # One-time setup script
├── run_evaluations.sh                 # Main evaluation runner
├── evaluators/                        # Custom evaluator configurations
│   ├── citation_quality.json          # Citation quality evaluator
│   ├── tool_selection.json            # Tool selection evaluator
│   ├── research_comprehensiveness.json # Research coverage evaluator
│   └── literature_search.json         # PubMed search evaluator
├── scripts/                           # Python evaluation scripts
│   ├── generate_test_sessions.py      # Generate test sessions
│   ├── run_single_evaluation.py       # Run single evaluation
│   └── run_batch_evaluations.py       # Run all evaluations
└── results/                           # Evaluation results (generated)
    ├── session_info.json              # Session information
    ├── eval_*.json                    # Individual results
    └── evaluation_summary_*.json      # Summary reports
```

## Prerequisites

1. **Research Agent Deployed**: Agent must be deployed to AgentCore Runtime with observability enabled
2. **AgentCore CLI**: Install the starter toolkit:
   ```bash
   pip install bedrock-agentcore-starter-toolkit
   ```
3. **Python 3.10+**: Required for evaluation scripts
4. **AWS Credentials**: Configured with appropriate permissions

## Quick Start

### 1. One-Time Setup

Create custom evaluators (run once):

```bash
cd agents_catalog/28-Research-agent-biomni-gateway-tools/evaluations
chmod +x setup_evaluators.sh
./setup_evaluators.sh
```

This creates four custom evaluators:
- `ResearchAgent.CitationQuality`
- `ResearchAgent.ToolSelection`
- `ResearchAgent.ResearchComprehensiveness`
- `ResearchAgent.LiteratureSearch`

### 2. Run Complete Evaluation

Execute the full evaluation suite:

```bash
chmod +x run_evaluations.sh
./run_evaluations.sh
```

This will:
1. Generate test sessions by invoking the agent with test queries
2. Wait 5 minutes for CloudWatch log propagation
3. Run all evaluations on all test cases
4. Generate summary report

**Expected Duration**: ~20-30 minutes for 4 test cases (depending on agent response time)

### 3. Review Results

Check the results directory:

```bash
ls -la results/

# View summary
cat results/evaluation_summary_*.json

# View individual test results
cat results/eval_tc_001_*.json
```

## Usage

### Run All Tests

```bash
./run_evaluations.sh
```

### Run Specific Test Case

```bash
./run_evaluations.sh --test-case tc_001
```

### Use Existing Sessions (Skip Generation)

```bash
./run_evaluations.sh --skip-session-gen
```

### Run Single Evaluation Manually

```bash
# Using latest session
python scripts/run_single_evaluation.py --auto

# Using specific session
python scripts/run_single_evaluation.py --session-id <session_id>

# With specific evaluators
python scripts/run_single_evaluation.py --auto --evaluators "Builtin.Helpfulness,ResearchAgent.CitationQuality"
```

## Test Cases

The framework includes 4 test cases from the agent's sample queries:

1. **tc_001: Trastuzumab Mechanism Analysis** (High Complexity)
   - Tests: Multi-database queries, protein structure, clinical trials, adverse events
   - Expected tools: PubMed, UniProt, DrugBank, OpenFDA, ClinicalTrials.gov

2. **tc_002: BRCA1 Variant Analysis** (High Complexity)
   - Tests: Genomic variant analysis, population genetics, clinical significance
   - Expected tools: PubMed, ClinVar, gnomAD, UniProt, ClinicalTrials.gov

3. **tc_003: PI3K/AKT/mTOR Pathway Investigation** (High Complexity)
   - Tests: Pathway analysis, protein interactions, therapeutic targets
   - Expected tools: PubMed, KEGG, Reactome, UniProt, DrugBank

4. **tc_004: Agent Capabilities Query** (Low Complexity)
   - Tests: Self-description, helpfulness
   - Expected tools: None (conversational)

## Evaluators

### Custom Evaluators

#### 1. Citation Quality (TRACE Level)
**ID**: `ResearchAgent.CitationQuality`

Evaluates citation formatting and reference accuracy:
- In-text numbered citations [1], [2], etc.
- Complete References section
- Proper academic format with PMIDs/DOIs
- Database source citations

**Rating Scale**: 0.0 (Poor) to 1.0 (Excellent)

#### 2. Tool Selection (TOOL_CALL Level)
**ID**: `ResearchAgent.ToolSelection`

Evaluates appropriate database tool selection:
- Relevance to research question
- Comprehensiveness (multiple complementary databases)
- Appropriate tool parameters
- Logical sequence

**Rating Scale**: 0.0 (Wrong Tools) to 1.0 (Optimal)

#### 3. Research Comprehensiveness (SESSION Level)
**ID**: `ResearchAgent.ResearchComprehensiveness`

Evaluates completeness of research coverage:
- All requirements addressed
- Appropriate depth of analysis
- Multi-database synthesis
- Clear conclusions

**Rating Scale**: 0.0 (Incomplete) to 1.0 (Comprehensive)

#### 4. Literature Search Effectiveness (TOOL_CALL Level)
**ID**: `ResearchAgent.LiteratureSearch`

Evaluates PubMed search quality:
- Appropriate search terms
- Scientific terminology
- Comprehensiveness
- Search strategy effectiveness

**Rating Scale**: 0.0 (Poor) to 1.0 (Excellent)

### Built-in Evaluators

The framework also uses AgentCore's built-in evaluators:
- `Builtin.Helpfulness` (TRACE)
- `Builtin.Correctness` (TRACE)
- `Builtin.GoalSuccessRate` (SESSION)
- `Builtin.Faithfulness` (TRACE)

## Understanding Results

### Summary Report Structure

```json
{
  "generated_at": "2025-01-09T12:00:00",
  "total_sessions_evaluated": 4,
  "successful_evaluations": 4,
  "failed_evaluations": 0,
  "average_scores": {
    "ResearchAgent.CitationQuality": {
      "average_score": 0.85,
      "min_score": 0.75,
      "max_score": 1.0,
      "num_evaluations": 4
    },
    // ... more evaluators
  },
  "results": [
    // Individual test case results
  ]
}
```

### Individual Result Structure

```json
{
  "test_case_id": "tc_001",
  "test_case_name": "Trastuzumab Mechanism Analysis",
  "session_id": "uuid",
  "status": "success",
  "metrics": {
    "ResearchAgent.CitationQuality": {
      "score": 0.85,
      "label": "Good"
    },
    // ... more metrics
  }
}
```

### Score Interpretation

- **0.0 - 0.25**: Poor performance, significant issues
- **0.25 - 0.5**: Below expectations, needs improvement
- **0.5 - 0.75**: Adequate performance, room for enhancement
- **0.75 - 0.9**: Good performance, minor improvements possible
- **0.9 - 1.0**: Excellent performance, meeting or exceeding expectations

## Troubleshooting

### "No spans found for session"

**Cause**: CloudWatch logs haven't propagated yet (2-5 minute delay)

**Solution**: 
```bash
# Wait longer, then retry
./run_evaluations.sh --skip-session-gen
```

### "AgentCore CLI not found"

**Solution**:
```bash
pip install bedrock-agentcore-starter-toolkit
```

### "Evaluator not found"

**Solution**:
```bash
# Re-run setup
./setup_evaluators.sh
```

### Agent invocation fails

**Check**:
1. Agent is deployed: `agentcore status`
2. AWS credentials are valid
3. Observability is enabled
4. Required SSM parameters exist

## Advanced Usage

### Custom Evaluator Modifications

Edit evaluator configurations in `evaluators/`:

```bash
# Modify evaluator
vi evaluators/citation_quality.json

# Update evaluator
agentcore eval evaluator update \
  --name "ResearchAgent.CitationQuality" \
  --config evaluators/citation_quality.json
```

### Add New Test Cases

Edit `test_queries.json`:

```json
{
  "id": "tc_005",
  "name": "New Test Case",
  "query": "Your test query here...",
  "expected_tools": ["tool1", "tool2"],
  "complexity": "high"
}
```

### Export Results for Analysis

```bash
# Convert to CSV for spreadsheet analysis
python -c "
import json, csv
with open('results/evaluation_summary_*.json') as f:
    data = json.load(f)
# ... processing code
"
```

### View in CloudWatch

1. Open [CloudWatch Console](https://console.aws.amazon.com/cloudwatch/)
2. Navigate to **GenAI Observability** → **Bedrock AgentCore**
3. Select your agent
4. View **Evaluations** tab for detailed trace-level results

## Best Practices

1. **Regular Evaluation**: Run evaluations after significant agent changes
2. **Baseline Tracking**: Keep summary reports to track improvement over time
3. **Test Case Expansion**: Add domain-specific test cases as needed
4. **Threshold Setting**: Define acceptable score thresholds for each evaluator
5. **CI/CD Integration**: Consider automating evaluations in deployment pipelines

## Performance Optimization

### Reduce Evaluation Time

```bash
# Run single test case
./run_evaluations.sh --test-case tc_001

# Skip CloudWatch wait (manual verification)
./run_evaluations.sh --skip-wait
```

### Parallel Execution

For large test suites, run evaluations in parallel:

```bash
# Generate all sessions first
python scripts/generate_test_sessions.py

# Run evaluations in parallel (separate terminals)
python scripts/run_single_evaluation.py --session-id <session1> &
python scripts/run_single_evaluation.py --session-id <session2> &
```

## References

- [AgentCore Evaluation Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations.html)
- [AgentCore Starter Toolkit](https://github.com/aws/bedrock-agentcore-starter-toolkit)
- [Research Agent Documentation](../README.md)

## Support

For issues or questions:
1. Check [Troubleshooting](#troubleshooting) section
2. Review AgentCore documentation
3. Check agent logs in CloudWatch
4. Verify AWS permissions and configuration

## License

This evaluation framework is part of the Research Agent project. See [LICENSE](../../LICENSE) for details.
