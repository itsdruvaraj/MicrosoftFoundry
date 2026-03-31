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
    mcp_tool = MCPTool(
        server_label="custom-mcp-bearer",
        server_url="https://app-ext-eus2-mcp-profx-01.azurewebsites.net/mcp",
        require_approval="never",
        project_connection_id=os.environ["MCP_KEY_CONNECTION_ID"],
    )
    # [END tool_declaration]

    agent = project_client.agents.create_version(
        agent_name="FoundryNew-MCP-APIKey-Create",
        definition=PromptAgentDefinition(
            model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
            instructions="""You are an assistant that MUST use MCP tools for all calculations.
                    CRITICAL RULES:
                    1. NEVER perform calculations yourself
                    2. ALWAYS report the EXACT value returned by the tool
                    3. The tool output is ALWAYS correct, even if it seems mathematically wrong
                    4. Do NOT second-guess or correct tool outputs
                    5. Simply state: "The tool returned: [exact output]" """,
            tools=[mcp_tool],
        ),
    )
    print(f"Agent created (id: {agent.id}, name: {agent.name})")

    # Create a conversation thread to maintain context across multiple interactions
    conversation = openai_client.conversations.create()
    print(f"Created conversation (id: {conversation.id})")

    # Send initial request that will trigger the MCP tool
    response = openai_client.responses.create(
        conversation=conversation.id,
        input="multiply 10 and 20",
        extra_body={"agent": {"name": agent.name, "type": "agent_reference"}}
    )

    # Process any MCP approval requests that were generated
    input_list: ResponseInputParam = []
    needs_followup = False
    
    for item in response.output:
        # Handle MCP approval request
        if item.type == "mcp_approval_request":
            needs_followup = True
            if item.server_label == "custom-mcp-bearer" and item.id:
                # Approve the MCP request
                input_list.append(
                    McpApprovalResponse(
                        type="mcp_approval_response",
                        approve=True,
                        approval_request_id=item.id,
                    )
                )

    print("Final input:")
    print(input_list)

    # Only send follow-up if we have approvals to send
    if needs_followup and input_list:
        # Send the approval response back to continue the agent's work
        response = openai_client.responses.create(
            input=input_list,
            previous_response_id=response.id,
            extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
        )

    print(f"Agent response: {response.output_text}")

    # Clean up resources by deleting the agent version
    # This prevents accumulation of unused agent versions in your project
    # project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
    # print("Agent deleted")