# pylint: disable=line-too-long,useless-suppression
# ------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------

"""
DESCRIPTION:
    This sample demonstrates how to run Prompt Agent operations
    using MCP (Model Context Protocol) tools and a synchronous client.

USAGE:
    python sample_agent_mcp.py

    Before running the sample:

    pip install "azure-ai-projects>=2.0.0b1" python-dotenv

    Set these environment variables with your own values:
    1) AZURE_AI_PROJECT_ENDPOINT - The Azure AI Project endpoint, as found in the Overview
       page of your Microsoft Foundry portal.
    2) AZURE_AI_MODEL_DEPLOYMENT_NAME - The deployment name of the AI model, as found under the "Name" column in
       the "Models + endpoints" tab in your Microsoft Foundry project.
"""

import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, MCPTool, Tool
from openai.types.responses.response_input_param import McpApprovalResponse, ResponseInputParam


load_dotenv()

endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]

with (
    DefaultAzureCredential() as credential,
    AIProjectClient(endpoint=endpoint, credential=credential) as project_client,
    project_client.get_openai_client() as openai_client,
):

    # Read the prompt from the file
    with open(os.path.join(os.path.dirname(__file__), "..", "Workflows", "agent-mapping-engine-prompt.txt"), "r", encoding="utf-8") as f:
        planner_instructions = f.read()

    # Add JSON requirement to instructions to satisfy json_object response format
    planner_instructions = planner_instructions + "\n\nIMPORTANT: Always respond in JSON format."

    agent = project_client.agents.create_version(
        agent_name="FoundryNew-MCP-DT-Planner",
        definition=PromptAgentDefinition(
            model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
            instructions=planner_instructions,
        ),
    )
    print(f"Agent created (id: {agent.id}, name: {agent.name})")