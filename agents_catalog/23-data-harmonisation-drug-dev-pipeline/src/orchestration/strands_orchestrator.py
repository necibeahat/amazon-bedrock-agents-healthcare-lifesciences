"""
Strands Framework Orchestrator for Multi-Agent Coordination

This module implements the main orchestrator using the Strands Agent SDK
to coordinate Web Scraper, Data Harmonizer, and Quality Assurance agents.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

from strands import Agent, tool
from strands.multiagent import Swarm, GraphBuilder
from strands.types.content import ContentBlock

from ..agents.web_scraper.agent import WebScraperAgent
from ..agents.data_harmonizer.agent import DataHarmonizerAgent
from ..agents.quality_assurance.agent import QualityAssuranceAgent
from ..models.pipeline import PipelineTask, TaskStatus, WorkflowState
from ..utils.logging import get_logger

logger = get_logger(__name__)


class AgentType(Enum):
    """Enumeration of agent types in the system."""
    WEB_SCRAPER = "web_scraper"
    DATA_HARMONIZER = "data_harmonizer"
    QUALITY_ASSURANCE = "quality_assurance"


@dataclass
class AgentResult:
    """Result from an agent execution."""
    agent_type: AgentType
    task_id: str
    success: bool
    data: Any
    error: Optional[str] = None
    execution_time: Optional[float] = None


@dataclass
class MetricsData:
    """Metrics data for monitoring."""
    task_executions: Dict[str, int]
    agent_performance: Dict[str, Dict[str, float]]
    error_counts: Dict[str, int]
    
    def __init__(self):
        self.task_executions = {}
        self.agent_performance = {}
        self.error_counts = {}
    
    def record_task_execution(self, task_id: str, agent_type: str, execution_time: float, status: str):
        """Record task execution metrics."""
        self.task_executions[task_id] = self.task_executions.get(task_id, 0) + 1
        
        if agent_type not in self.agent_performance:
            self.agent_performance[agent_type] = {"total_time": 0.0, "count": 0, "avg_time": 0.0}
        
        perf = self.agent_performance[agent_type]
        perf["total_time"] += execution_time
        perf["count"] += 1
        perf["avg_time"] = perf["total_time"] / perf["count"]
        
        if status == "error":
            self.error_counts[agent_type] = self.error_counts.get(agent_type, 0) + 1
    
    def get_pipeline_metrics(self) -> Dict[str, Any]:
        """Get comprehensive pipeline metrics."""
        return {
            "task_executions": self.task_executions,
            "agent_performance": self.agent_performance,
            "error_counts": self.error_counts,
            "total_tasks": sum(self.task_executions.values()),
            "total_errors": sum(self.error_counts.values())
        }


class PipelineOrchestrator:
    """
    Main orchestrator for the pharmaceutical pipeline multi-agent system.
    
    Implements ReWOO (Reasoning Without Observation) pattern using Strands framework:
    1. Planning Stage: Create structured execution plan
    2. Execution Stage: Coordinate agent execution using Swarm or Graph patterns
    3. Synthesis Stage: Combine and validate results
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the pipeline orchestrator.
        
        Args:
            config: Configuration dictionary containing agent settings
        """
        self.config = config
        self.metrics_collector = MetricsData()
        
        # Initialize Strands agents
        self.agents: Dict[AgentType, Agent] = {}
        self._initialize_strands_agents()
        
        # Create multi-agent orchestration patterns
        self.swarm: Optional[Swarm] = None
        self.graph = None
        self._setup_orchestration_patterns()
        
        # Workflow state tracking
        self.current_workflow: Optional[WorkflowState] = None
        
        logger.info("Pipeline orchestrator initialized with Strands framework")
    
    def _initialize_strands_agents(self) -> None:
        """Initialize all agents using Strands Agent SDK."""
        try:
            # Web Scraper Agent
            @tool
            def collect_pipeline_data(url: str) -> Dict[str, Any]:
                """
                Collect pharmaceutical pipeline data from a company website.
                
                Args:
                    url: The URL to scrape data from
                    
                Returns:
                    Dictionary containing collected pipeline data
                """
                # This would integrate with the actual WebScraperAgent
                web_scraper = WebScraperAgent(self.config.get("web_scraper", {}))
                return web_scraper.collect_data(url)
            
            self.agents[AgentType.WEB_SCRAPER] = Agent(
                name="web_scraper",
                system_prompt="""You are a Web Scraper Agent specialized in collecting pharmaceutical pipeline data from company websites.
                
Your responsibilities:
- Check robots.txt compliance before scraping
- Extract pipeline data including compound names, indications, development phases
- Respect rate limits and implement polite crawling
- Validate collected data and preserve metadata
- Handle errors gracefully and provide detailed logging

Always ensure ethical data collection practices and compliance with website terms.""",
                tools=[collect_pipeline_data],
                callback_handler=None  # Suppress intermediate output
            )
            
            # Data Harmonizer Agent
            @tool
            def harmonize_pipeline_data(raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
                """
                Harmonize and standardize pharmaceutical pipeline data.
                
                Args:
                    raw_data: List of raw data dictionaries from different sources
                    
                Returns:
                    Dictionary containing harmonized data
                """
                # This would integrate with the actual DataHarmonizerAgent
                harmonizer = DataHarmonizerAgent(self.config.get("data_harmonizer", {}))
                return harmonizer.harmonize_data(raw_data)
            
            @tool
            def apply_ontology_mapping(data: Dict[str, Any]) -> Dict[str, Any]:
                """
                Apply biomedical ontology mappings to pharmaceutical data.
                
                Args:
                    data: Data to apply ontology mappings to
                    
                Returns:
                    Data enriched with ontology mappings
                """
                harmonizer = DataHarmonizerAgent(self.config.get("data_harmonizer", {}))
                return harmonizer.apply_ontologies(data)
            
            self.agents[AgentType.DATA_HARMONIZER] = Agent(
                name="data_harmonizer",
                system_prompt="""You are a Data Harmonizer Agent specialized in standardizing pharmaceutical pipeline data.

Your responsibilities:
- Analyze schemas from different data sources
- Create unified data models that accommodate all source variations
- Apply biomedical ontologies (MONDO, ChEBI, EFO, NCIT, MeSH, ATC, ICD-10, SNOMED CT)
- Resolve duplicate entries across sources
- Enrich data with additional metadata and classifications
- Document field mappings and transformations

Ensure data consistency and semantic enrichment for downstream analysis.""",
                tools=[harmonize_pipeline_data, apply_ontology_mapping],
                callback_handler=None
            )
            
            # Quality Assurance Agent
            @tool
            def assess_data_quality(data: Dict[str, Any]) -> Dict[str, Any]:
                """
                Perform comprehensive data quality assessment.
                
                Args:
                    data: Data to assess for quality
                    
                Returns:
                    Dictionary containing quality assessment results
                """
                # This would integrate with the actual QualityAssuranceAgent
                qa_agent = QualityAssuranceAgent(self.config.get("quality_assurance", {}))
                return qa_agent.assess_quality(data)
            
            @tool
            def detect_anomalies(data: Dict[str, Any]) -> Dict[str, Any]:
                """
                Detect anomalies and outliers in pharmaceutical data.
                
                Args:
                    data: Data to analyze for anomalies
                    
                Returns:
                    Dictionary containing anomaly detection results
                """
                qa_agent = QualityAssuranceAgent(self.config.get("quality_assurance", {}))
                return qa_agent.detect_anomalies(data)
            
            @tool
            def generate_quality_report(assessments: List[Dict[str, Any]]) -> Dict[str, Any]:
                """
                Generate comprehensive data quality report.
                
                Args:
                    assessments: List of quality assessment results
                    
                Returns:
                    Dictionary containing comprehensive quality report
                """
                qa_agent = QualityAssuranceAgent(self.config.get("quality_assurance", {}))
                return qa_agent.generate_report(assessments)
            
            self.agents[AgentType.QUALITY_ASSURANCE] = Agent(
                name="quality_assurance",
                system_prompt="""You are a Quality Assurance Agent specialized in pharmaceutical data quality assessment.

Your responsibilities:
- Perform completeness checks on all required fields
- Validate data consistency across sources
- Check data accuracy using external reference sources
- Identify outliers and anomalies in datasets
- Generate comprehensive quality reports
- Flag critical issues requiring human review
- Create actionable recommendations for data improvement

Ensure high data quality standards for reliable downstream analysis.""",
                tools=[assess_data_quality, detect_anomalies, generate_quality_report],
                callback_handler=None
            )
            
            logger.info(f"Initialized {len(self.agents)} Strands agents successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Strands agents: {e}")
            raise
    
    def _setup_orchestration_patterns(self) -> None:
        """Set up Strands multi-agent orchestration patterns."""
        try:
            # Create a Swarm for collaborative agent coordination
            agent_list = list(self.agents.values())
            self.swarm = Swarm(
                agent_list,  # First parameter is the list of agents
                entry_point=self.agents[AgentType.WEB_SCRAPER],  # Start with web scraper
                max_handoffs=20,
                max_iterations=20,
                execution_timeout=900.0,  # 15 minutes
                node_timeout=300.0,       # 5 minutes per agent
                repetitive_handoff_detection_window=8,
                repetitive_handoff_min_unique_agents=3
            )
            
            # Create a Graph for structured workflow execution
            builder = GraphBuilder()
            
            # Add agents as nodes
            builder.add_node(self.agents[AgentType.WEB_SCRAPER], "web_scraper")
            builder.add_node(self.agents[AgentType.DATA_HARMONIZER], "data_harmonizer")
            builder.add_node(self.agents[AgentType.QUALITY_ASSURANCE], "quality_assurance")
            
            # Define dependencies: web_scraper -> data_harmonizer -> quality_assurance
            builder.add_edge("web_scraper", "data_harmonizer")
            builder.add_edge("data_harmonizer", "quality_assurance")
            
            # Set entry point
            builder.set_entry_point("web_scraper")
            
            # Configure execution limits
            builder.set_execution_timeout(600)  # 10 minutes
            builder.set_node_timeout(300)       # 5 minutes per node
            
            # Build the graph
            self.graph = builder.build()
            
            logger.info("Multi-agent orchestration patterns configured successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup orchestration patterns: {e}")
            raise
    
    async def execute_pipeline(self, sources: List[str]) -> Dict[str, Any]:
        """
        Execute the complete pharmaceutical data pipeline using Strands orchestration.
        
        Args:
            sources: List of pharmaceutical company URLs to process
            
        Returns:
            Dictionary containing pipeline execution results
        """
        logger.info(f"Starting Strands pipeline execution for {len(sources)} sources")
        
        try:
            # Stage 1: Planning
            workflow_plan = await self._create_workflow_plan(sources)
            self.current_workflow = WorkflowState(
                id=f"pipeline_{datetime.now().isoformat()}",
                plan=workflow_plan,
                status=TaskStatus.RUNNING,
                start_time=datetime.now()
            )
            
            # Stage 2: Execution using Strands orchestration patterns
            execution_mode = self.config.get("execution_mode", "graph")  # "graph" or "swarm"
            
            if execution_mode == "swarm":
                results = await self._execute_with_swarm(sources)
            else:
                results = await self._execute_with_graph(sources)
            
            # Stage 3: Synthesis
            final_result = await self._synthesize_results(results)
            
            self.current_workflow.status = TaskStatus.COMPLETED
            self.current_workflow.end_time = datetime.now()
            
            logger.info("Strands pipeline execution completed successfully")
            return final_result
            
        except Exception as e:
            logger.error(f"Strands pipeline execution failed: {e}")
            if self.current_workflow:
                self.current_workflow.status = TaskStatus.FAILED
                self.current_workflow.error = str(e)
            raise
    
    async def _execute_with_swarm(self, sources: List[str]) -> Dict[str, Any]:
        """
        Execute pipeline using Strands Swarm pattern for collaborative agent coordination.
        
        Args:
            sources: List of source URLs to process
            
        Returns:
            Dictionary containing execution results
        """
        logger.info("Executing pipeline with Strands Swarm pattern")
        
        # Create task description for the swarm
        task_description = f"""
        Collect and process pharmaceutical pipeline data from the following sources:
        {', '.join(sources)}
        
        Process:
        1. Web Scraper Agent: Collect data from each source with robots.txt compliance
        2. Data Harmonizer Agent: Standardize and enrich the collected data
        3. Quality Assurance Agent: Assess data quality and generate reports
        
        Ensure all data is properly validated and meets quality standards.
        """
        
        # Execute the swarm
        swarm_result = await self.swarm.invoke_async(task_description)
        
        # Extract results from swarm execution
        results = {
            "swarm_status": swarm_result.status.value,
            "execution_time": swarm_result.execution_time,
            "node_history": [node.node_id for node in swarm_result.node_history],
            "results": {}
        }
        
        # Extract individual agent results
        for node_id, node_result in swarm_result.results.items():
            results["results"][node_id] = {
                "status": node_result.status.value,
                "result": str(node_result.result.message.content[0].text) if node_result.result else None,
                "execution_time": node_result.execution_time
            }
        
        return results
    
    async def _execute_with_graph(self, sources: List[str]) -> Dict[str, Any]:
        """
        Execute pipeline using Strands Graph pattern for structured workflow execution.
        
        Args:
            sources: List of source URLs to process
            
        Returns:
            Dictionary containing execution results
        """
        logger.info("Executing pipeline with Strands Graph pattern")
        
        # Create task description for the graph
        task_description = f"""
        Process pharmaceutical pipeline data from these sources: {', '.join(sources)}
        
        Follow this structured workflow:
        1. Collect data from all sources with proper compliance checks
        2. Harmonize and standardize the collected data
        3. Perform comprehensive quality assessment
        
        Ensure each step is completed before proceeding to the next.
        """
        
        # Execute the graph
        graph_result = await self.graph.invoke_async(task_description)
        
        # Extract results from graph execution
        results = {
            "graph_status": graph_result.status.value,
            "execution_time": graph_result.execution_time,
            "execution_order": [node.node_id for node in graph_result.execution_order],
            "results": {}
        }
        
        # Extract individual node results
        for node_id, node_result in graph_result.results.items():
            results["results"][node_id] = {
                "status": node_result.status.value,
                "result": str(node_result.result.message.content[0].text) if node_result.result else None,
                "execution_time": node_result.execution_time
            }
        
        return results
    
    async def _create_workflow_plan(self, sources: List[str]) -> List[PipelineTask]:
        """
        Create a structured execution plan for the pipeline.
        
        Args:
            sources: List of source URLs to process
            
        Returns:
            List of pipeline tasks with dependencies
        """
        tasks = []
        
        # Phase 1: Data Collection Tasks
        collection_tasks = []
        for i, source in enumerate(sources):
            task = PipelineTask(
                id=f"collect_{i}",
                agent_type=AgentType.WEB_SCRAPER,
                action="collect_data",
                parameters={"url": source},
                dependencies=[],
                priority=1
            )
            collection_tasks.append(task)
            tasks.append(task)
        
        # Phase 2: Data Harmonization Task
        harmonization_task = PipelineTask(
            id="harmonize_data",
            agent_type=AgentType.DATA_HARMONIZER,
            action="harmonize_data",
            parameters={"source_tasks": [t.id for t in collection_tasks]},
            dependencies=[t.id for t in collection_tasks],
            priority=2
        )
        tasks.append(harmonization_task)
        
        # Phase 3: Quality Assurance Task
        qa_task = PipelineTask(
            id="quality_assessment",
            agent_type=AgentType.QUALITY_ASSURANCE,
            action="assess_quality",
            parameters={"harmonized_data_task": harmonization_task.id},
            dependencies=[harmonization_task.id],
            priority=3
        )
        tasks.append(qa_task)
        
        logger.info(f"Created workflow plan with {len(tasks)} tasks")
        return tasks
    
    async def _synthesize_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesize and validate final pipeline results.
        
        Args:
            results: Dictionary of execution results
            
        Returns:
            Synthesized final results
        """
        logger.info("Synthesizing Strands pipeline results")
        
        # Extract execution metadata
        execution_mode = "swarm" if "swarm_status" in results else "graph"
        status = results.get("swarm_status") or results.get("graph_status")
        execution_time = results.get("execution_time", 0)
        
        # Extract agent results
        agent_results = results.get("results", {})
        
        # Calculate quality metrics
        successful_agents = sum(1 for r in agent_results.values() if r.get("status") == "COMPLETED")
        total_agents = len(agent_results)
        success_rate = (successful_agents / total_agents * 100) if total_agents > 0 else 0
        
        # Create comprehensive result summary
        final_result = {
            "pipeline_id": self.current_workflow.id if self.current_workflow else "unknown",
            "execution_summary": {
                "execution_mode": execution_mode,
                "status": status,
                "execution_time_ms": execution_time,
                "success_rate": success_rate,
                "successful_agents": successful_agents,
                "total_agents": total_agents
            },
            "agent_results": agent_results,
            "metrics": self.metrics_collector.get_pipeline_metrics(),
            "timestamp": datetime.now().isoformat()
        }
        
        # Record final metrics
        self.metrics_collector.record_task_execution(
            "pipeline_synthesis", 
            "orchestrator", 
            execution_time / 1000.0,  # Convert to seconds
            "success" if status == "COMPLETED" else "error"
        )
        
        logger.info(f"Pipeline synthesis completed. Success rate: {success_rate:.1f}%")
        return final_result
    
    async def get_workflow_status(self) -> Optional[Dict[str, Any]]:
        """
        Get current workflow status.
        
        Returns:
            Dictionary containing workflow status information
        """
        if not self.current_workflow:
            return None
        
        return {
            "workflow_id": self.current_workflow.id,
            "status": self.current_workflow.status.value,
            "start_time": self.current_workflow.start_time.isoformat(),
            "end_time": self.current_workflow.end_time.isoformat() if self.current_workflow.end_time else None,
            "tasks": [
                {
                    "id": task.id,
                    "agent": task.agent_type.value,
                    "action": task.action,
                    "status": task.status.value,
                    "start_time": task.start_time.isoformat() if task.start_time else None,
                    "end_time": task.end_time.isoformat() if task.end_time else None,
                    "error": task.error
                }
                for task in self.current_workflow.plan
            ]
        }
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the orchestrator and all agents."""
        logger.info("Shutting down Strands pipeline orchestrator")
        
        try:
            # No explicit shutdown needed for Strands agents
            # They are managed by the Strands framework
            logger.info("Strands agents managed by framework - no explicit shutdown required")
            
        except Exception as e:
            logger.error(f"Error during orchestrator shutdown: {e}")
        
        logger.info("Strands pipeline orchestrator shutdown completed")