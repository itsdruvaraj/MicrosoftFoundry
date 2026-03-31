# pylint: disable=line-too-long,useless-suppression
# ------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------

"""
DESCRIPTION:
    This sample demonstrates how to create a multi-agent workflow using a synchronous client
    with FoundryNew-MCP-DT-Planner running first, then FoundryNew-MCP-DT-ValidateUser in sequence.

USAGE:
    python workflow-planner-validateuser.py

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
from azure.ai.projects.models import (
    ResponseStreamEventType,
    WorkflowAgentDefinition,
    ItemType,
)

load_dotenv()

endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]

with (
    DefaultAzureCredential() as credential,
    AIProjectClient(endpoint=endpoint, credential=credential) as project_client,
    project_client.get_openai_client() as openai_client,
):
    # Define agent names (these agents should already exist in your project)
    planner_agent_name = "FoundryNew-MCP-DT-Planner"
    validate_user_agent_name = "FoundryNew-MCP-DT-ValidateUser"

    # Create Multi-Agent Sequential Workflow
    workflow_yaml = f"""
kind: workflow
trigger:
  kind: OnConversationStart
  id: planner_validateuser_workflow
  actions:
    - kind: CreateConversation
      id: create_planner_conversation
      conversationId: Local.PlannerConversationId

    - kind: InvokeAzureAgent
      id: planner_agent
      description: The planner agent processes the request first
      conversationId: "=Local.PlannerConversationId"
      agent:
        name: {planner_agent_name}
        version: "13"
      input:
        text: "=concat('Please respond in JSON format. User request: ', System.LastMessageText)"

    - kind: CreateConversation
      id: create_validate_conversation
      conversationId: Local.ValidateConversationId

    - kind: InvokeAzureAgent
      id: validateuser_agent
      description: The validate user agent processes the planner output
      conversationId: "=Local.ValidateConversationId"
      agent:
        name: {validate_user_agent_name}
        version: "7"
      input:
        kind: text
        text: "Validate the user based on this plan. Respond in JSON format."

    - kind: EndConversation
      id: end_workflow
"""

    workflow = project_client.agents.create_version(
        agent_name="FoundryNew-Workflow-Planner-ValidateUser",
        definition=WorkflowAgentDefinition(workflow=workflow_yaml),
    )
    print(f"Workflow created (id: {workflow.id}, name: {workflow.name}, version: {workflow.version})")

    # Create a conversation and run the workflow
    conversation = openai_client.conversations.create()
    print(f"Created conversation (id: {conversation.id})")

    # Example input - modify as needed
    user_input = "Please validate the user (druvan) and create a plan for solution version in json format"

    stream = openai_client.responses.create(
        conversation=conversation.id,
        extra_body={"agent": {"name": workflow.name, "type": "agent_reference"}},
        input=user_input,
        stream=True,
        metadata={"x-ms-debug-mode-enabled": "1"},
    )

    for event in stream:
        print(f"Event {event.sequence_number} type '{event.type}'", end="")
        if (
            event.type == ResponseStreamEventType.RESPONSE_OUTPUT_ITEM_ADDED
            or event.type == ResponseStreamEventType.RESPONSE_OUTPUT_ITEM_DONE
        ) and event.item.type == ItemType.WORKFLOW_ACTION:
            print(
                f": item action ID '{event.item.action_id}' is '{event.item.status}' (previous action ID: '{event.item.previous_action_id}')",
                end="",
            )
        elif event.type == ResponseStreamEventType.RESPONSE_FAILED:
            print(f" - Error: {event.response.error if hasattr(event, 'response') and hasattr(event.response, 'error') else event}", end="")
        print("", flush=True)

    # # Cleanup
    # openai_client.conversations.delete(conversation_id=conversation.id)
    # print("Conversation deleted")

    # project_client.agents.delete_version(agent_name=workflow.name, agent_version=workflow.version)
    # print("Workflow deleted")
