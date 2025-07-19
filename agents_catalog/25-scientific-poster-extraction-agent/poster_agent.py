from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from strands_tools import file_read, file_write, shell
import urllib3
import os

# Disable SSL warnings (only use in development environments)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Documentation MCP client
docs_client = MCPClient(lambda: stdio_client(
    StdioServerParameters(
        command="uvx", 
        args=["awslabs.aws-documentation-mcp-server@latest"]
    )
))

# Bedrock Data Automation client
aws_bda_client = MCPClient(
    lambda: stdio_client(
        StdioServerParameters(
            command="uvx", 
            args=["awslabs.aws-bedrock-data-automation-mcp-server@latest"],
        )
    )
)

bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    temperature=0.7,
)

SYSTEM_PROMPT = """
You are an expert clinical analyst. //
Your role is to extract text from posters. //
Create a blueprint for the poster. //
Extract text from each section title, authors, introduction, methods, results and summary. //
Extract data from each figure in CSV format. 
"""

# Use only the clients that are working
with aws_bda_client, docs_client:
    all_tools = aws_bda_client.list_tools_sync() + docs_client.list_tools_sync()
    agent = Agent(tools=[all_tools, file_read, file_write, shell], model=bedrock_model, system_prompt=SYSTEM_PROMPT)

    response = agent(
        "Using Bedrock Data Automation, extract the text from data/SP00240-Isolation_of_Tumor_Infiltrating_Leukocytes_from_Mouse_Tumors.pdf" \
        "Download the output to data/output",
    )
    print(response)

