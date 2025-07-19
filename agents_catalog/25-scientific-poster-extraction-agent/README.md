# Scientific Poster Extraction Agent

## Overview
The Scientific Poster Extraction Agent is a specialized AI tool designed to extract and analyze text and data from scientific posters. It leverages Amazon Bedrock Data Automation and Claude 3.5 Sonnet to process poster content in various formats, primarily PDFs.

## Key Features
- **Text Extraction**: Automatically extracts text from poster sections including titles, authors, introduction, methods, results, and summary
- **Data Extraction**: Converts figure data into structured CSV format
- **Multi-Format Support**: Works with PDFs, images, and potentially video formats
- **Structured Output**: Organizes extracted information for downstream analysis

## Technical Architecture
- **Foundation Model**: Anthropic Claude 3.5 Sonnet (via Amazon Bedrock)
- **Framework**: Strands Agents SDK for agent creation and management
- **Tools Integration**: Model Context Protocol (MCP) for tool integration
- **Data Processing**: Amazon Bedrock Data Automation for document processing

## Use Cases
- **Conference Research**: Quickly digitize and analyze scientific posters from conferences
- **Literature Review**: Extract structured data from multiple posters for comparative analysis
- **Knowledge Management**: Build searchable databases of scientific poster content
- **Research Acceleration**: Automate the extraction of key findings from scientific posters

## Implementation Details
The agent is implemented using:
- Strands Agents SDK for agent orchestration
- MCP clients for AWS documentation and Bedrock Data Automation
- File operations for saving extracted data
- Claude 3.5 Sonnet for natural language understanding and extraction

## Sample Workflow
1. User provides a scientific poster in PDF format
2. Agent processes the poster using Bedrock Data Automation
3. Text is extracted from all relevant sections
4. Figure data is converted to CSV format
5. Results are saved to the specified output location
6. User can query the extracted content

## Requirements
- AWS account with access to Amazon Bedrock
- Permissions for Claude 3.5 Sonnet model
- Python environment with required dependencies
- Access to Bedrock Data Automation

## Sample Data
The example uses a sample scientific poster downloaded from:
https://cdn.stemcell.com/media/files/poster/SP00240-Isolation_of_Tumor_Infiltrating_Leukocytes_from_Mouse_Tumors.pdf

This is a sample poster for demonstration purposes. Bedrock Data Automation supports various formats including images, documents, and videos for extraction and analysis.

## How to Run
To run the Scientific Poster Extraction Agent, use the following command in your terminal:

```bash
python3 poster_agent.py
```

This will execute the agent, which will process the sample poster PDF located in the data directory and save the extracted information to the output folder.

## Next Steps
Future development of this agent will focus on deployment with Amazon Bedrock AgentCore. This will enable:

- **Simplified Deployment**: Streamlined deployment process for production environments
- **Scalable Infrastructure**: Built-in scaling capabilities for handling multiple concurrent requests
- **Enhanced Security**: Enterprise-grade security features for handling sensitive medical data
- **Monitoring & Observability**: Comprehensive monitoring and logging capabilities

For more information about Amazon Bedrock AgentCore, visit: https://aws.amazon.com/bedrock/agentcore/