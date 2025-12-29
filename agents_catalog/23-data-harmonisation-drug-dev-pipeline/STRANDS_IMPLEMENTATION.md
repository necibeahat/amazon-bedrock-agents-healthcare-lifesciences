# Strands Agent SDK Implementation

This document describes the implementation of multi-agent orchestration using the **Strands Agent SDK** for the pharmaceutical pipeline data engineering system.

## Overview

The system has been updated to use the actual Strands Agent SDK instead of mock implementations, providing:

- **Real Strands Agents**: Web Scraper, Data Harmonizer, and Quality Assurance agents implemented as Strands Agent instances
- **Multi-Agent Orchestration**: Support for both Swarm and Graph patterns from Strands framework
- **Agent Communication**: Proper agent-to-agent communication using Strands messaging
- **Error Handling**: Comprehensive error handling and recovery mechanisms
- **Monitoring**: Centralized monitoring and metrics collection for Strands agents

## Architecture

### Strands Agent Components

#### 1. Web Scraper Agent
```python
Agent(
    name="web_scraper",
    system_prompt="You are a Web Scraper Agent specialized in collecting pharmaceutical pipeline data...",
    tools=[collect_pipeline_data],
    callback_handler=None
)
```

**Responsibilities:**
- Check robots.txt compliance before scraping
- Extract pipeline data from pharmaceutical company websites
- Respect rate limits and implement polite crawling
- Validate collected data and preserve metadata

#### 2. Data Harmonizer Agent
```python
Agent(
    name="data_harmonizer", 
    system_prompt="You are a Data Harmonizer Agent specialized in standardizing pharmaceutical pipeline data...",
    tools=[harmonize_pipeline_data, apply_ontology_mapping],
    callback_handler=None
)
```

**Responsibilities:**
- Analyze schemas from different data sources
- Create unified data models
- Apply biomedical ontologies (MONDO, ChEBI, EFO, NCIT, MeSH, ATC, ICD-10, SNOMED CT)
- Resolve duplicate entries across sources

#### 3. Quality Assurance Agent
```python
Agent(
    name="quality_assurance",
    system_prompt="You are a Quality Assurance Agent specialized in pharmaceutical data quality assessment...",
    tools=[assess_data_quality, detect_anomalies, generate_quality_report],
    callback_handler=None
)
```

**Responsibilities:**
- Perform completeness checks on required fields
- Validate data consistency across sources
- Check data accuracy using external references
- Identify outliers and anomalies

### Orchestration Patterns

#### Graph Pattern (Structured Workflow)
```python
# Sequential execution: web_scraper -> data_harmonizer -> quality_assurance
builder = GraphBuilder()
builder.add_node(web_scraper_agent, "web_scraper")
builder.add_node(data_harmonizer_agent, "data_harmonizer") 
builder.add_node(quality_assurance_agent, "quality_assurance")
builder.add_edge("web_scraper", "data_harmonizer")
builder.add_edge("data_harmonizer", "quality_assurance")
graph = builder.build()
```

**Use Cases:**
- Deterministic workflow execution
- Clear dependency management
- Structured data processing pipeline

#### Swarm Pattern (Collaborative Agents)
```python
# Collaborative execution with autonomous handoffs
swarm = Swarm(
    agents=[web_scraper_agent, data_harmonizer_agent, quality_assurance_agent],
    entry_point=web_scraper_agent,
    max_handoffs=20,
    max_iterations=20
)
```

**Use Cases:**
- Dynamic task distribution
- Collaborative problem solving
- Emergent workflow patterns

## Implementation Details

### Core Components

#### 1. PipelineOrchestrator (`strands_orchestrator.py`)
- **Purpose**: Main orchestrator using Strands Agent SDK
- **Key Features**:
  - Initializes Strands agents with proper tools and system prompts
  - Supports both Swarm and Graph execution patterns
  - Implements ReWOO (Reasoning Without Observation) pattern
  - Provides comprehensive metrics collection

#### 2. AgentCommunicationManager (`communication.py`)
- **Purpose**: Manages communication between Strands agents
- **Key Features**:
  - Registers Strands agents for communication
  - Sets up Swarm and Graph communication patterns
  - Handles message routing and response tracking
  - Provides communication metrics and monitoring

#### 3. IntegratedOrchestrationSystem (`integration.py`)
- **Purpose**: Unified interface for the complete system
- **Key Features**:
  - Integrates all orchestration components
  - Provides multiple execution modes (Graph, Swarm, Main)
  - Comprehensive system status and metrics
  - Error handling and recovery

### Execution Modes

#### 1. Graph Execution
```python
result = await system.execute_pipeline_with_graph(sources)
```
- Structured workflow with explicit dependencies
- Deterministic execution order
- Suitable for well-defined processes

#### 2. Swarm Execution  
```python
result = await system.execute_pipeline_with_swarm(sources)
```
- Collaborative agent coordination
- Dynamic task handoffs
- Suitable for complex problem-solving

#### 3. Main Orchestrator
```python
result = await system.execute_pipeline(sources)
```
- Uses configured execution mode (Graph or Swarm)
- Comprehensive result synthesis
- Full pipeline metrics and monitoring

## Configuration

### System Configuration
```python
config = {
    "orchestrator": {
        "execution_mode": "graph",  # "graph" or "swarm"
        "web_scraper_concurrency": 3,
        "harmonizer_concurrency": 2,
        "qa_concurrency": 1
    },
    "communication": {
        "timeout": 300,
        "retry_attempts": 3
    },
    "workflow": {
        "max_concurrent_tasks": 5,
        "task_timeout": 600
    },
    "error_handling": {
        "max_retries": 3,
        "retry_delay": 5
    },
    "monitoring": {
        "metrics_retention_hours": 24,
        "alert_threshold": 5
    }
}
```

### Agent Configuration
Each Strands agent is configured with:
- **System Prompt**: Defines agent role and responsibilities
- **Tools**: Specific functions the agent can execute
- **Callback Handler**: Set to `None` to suppress intermediate output

## Usage Examples

### Basic Usage
```python
from src.orchestration.integration import IntegratedOrchestrationSystem

# Initialize system
system = IntegratedOrchestrationSystem(config)

# Start system
await system.start()

# Execute pipeline
sources = [
    "https://www.merck.com/research/product-pipeline/",
    "https://www.novonordisk.com/science-and-technology/r-d-pipeline.html"
]

result = await system.execute_pipeline(sources)

# Stop system
await system.stop()
```

### Pattern-Specific Execution
```python
# Execute with Graph pattern
graph_result = await system.execute_pipeline_with_graph(sources)

# Execute with Swarm pattern  
swarm_result = await system.execute_pipeline_with_swarm(sources)
```

### System Monitoring
```python
# Get system status
status = await system.get_system_status()

print(f"Framework: {status['framework']}")
print(f"Agents: {list(status['strands_agents'].keys())}")
print(f"Patterns: {status['orchestration_patterns']}")
```

## Demo Script

Run the demo script to see the Strands implementation in action:

```bash
python demo_strands_orchestration.py
```

The demo demonstrates:
- System initialization with Strands agents
- Graph pattern execution
- Swarm pattern execution
- Main orchestrator execution
- System status and metrics

## Key Benefits

### 1. Real Agent Framework
- Uses actual Strands Agent SDK instead of mock implementations
- Proper agent lifecycle management
- Native Strands tool integration

### 2. Multiple Orchestration Patterns
- Graph pattern for structured workflows
- Swarm pattern for collaborative problem-solving
- Flexible execution based on requirements

### 3. Comprehensive Monitoring
- Agent health monitoring
- Communication metrics
- Error tracking and recovery
- Performance metrics

### 4. Production Ready
- Proper error handling and recovery
- Configurable timeouts and retries
- Comprehensive logging and monitoring
- Scalable architecture

## Requirements Satisfaction

This implementation satisfies the following requirements:

### Requirement 5.1: Strands Framework Usage
✅ **Implemented**: Uses actual Strands Agent SDK for multi-agent orchestration

### Requirement 5.2: Agent Implementation  
✅ **Implemented**: Web Scraper, Data Harmonizer, and Quality Assurance agents as Strands agents

### Requirement 5.3: Communication Protocols
✅ **Implemented**: Strands messaging and orchestration patterns (Swarm, Graph)

### Requirement 5.4: Workflow Coordination
✅ **Implemented**: Proper task sequencing using Graph pattern and collaborative coordination using Swarm pattern

### Requirement 5.5: Error Handling
✅ **Implemented**: Graceful agent failure handling with retry mechanisms and recovery strategies

### Requirement 5.6: Centralized Monitoring
✅ **Implemented**: Comprehensive logging and monitoring for all Strands agent activities

## Next Steps

1. **Integration Testing**: Test with actual pharmaceutical websites
2. **Performance Optimization**: Tune agent configurations for optimal performance
3. **AgentCore Deployment**: Deploy to AWS Bedrock AgentCore for production use
4. **Observability Enhancement**: Add more detailed metrics and tracing
5. **Security Implementation**: Add authentication and authorization for agent communication

## Troubleshooting

### Common Issues

1. **Agent Initialization Failures**
   - Check Strands SDK installation
   - Verify agent configuration parameters
   - Review system prompts and tool definitions

2. **Communication Timeouts**
   - Increase timeout values in configuration
   - Check network connectivity
   - Review agent response times

3. **Pattern Execution Failures**
   - Verify agent dependencies are properly configured
   - Check for circular dependencies in Graph pattern
   - Review Swarm handoff limits and detection settings

### Debug Mode
Enable debug logging for detailed troubleshooting:
```python
import logging
logging.getLogger("strands.multiagent").setLevel(logging.DEBUG)
```

## Conclusion

The Strands Agent SDK implementation provides a robust, production-ready multi-agent orchestration system for pharmaceutical pipeline data processing. It leverages the full capabilities of the Strands framework while maintaining comprehensive error handling, monitoring, and flexibility in execution patterns.