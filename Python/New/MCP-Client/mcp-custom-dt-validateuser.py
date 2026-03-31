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
    # [START tool_declaration]
    # For MCP servers requiring authentication, use project_connection_id
    # Create a Custom Keys connection in Azure AI Foundry with:
    #   Key: "Authorization", Value: "Bearer <your-token>"
    # NOTE: Do NOT use allowed_tools in workflows - it causes serialization errors
    # Instead, guide the agent via instructions to use specific tools
    mcp_tool = MCPTool(
        server_label="custom-mcp-bearer",
        server_url="https://app-ext-eus2-mcp-profx-01.azurewebsites.net/mcp",
        require_approval="never",
        project_connection_id=os.environ["MCP_KEY_CONNECTION_ID"],
    )
    # [END tool_declaration]

    agent = project_client.agents.create_version(
        agent_name="FoundryNew-MCP-DT-ValidateUser",
        definition=PromptAgentDefinition(
            model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
            instructions="You are a user validation agent. Use the validate_user MCP tool to validate users. Respond in JSON format.",
            tools=[mcp_tool],
        ),
    )
    print(f"Agent created (id: {agent.id}, name: {agent.name})")