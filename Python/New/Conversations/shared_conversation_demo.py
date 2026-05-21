# ------------------------------------
# Demo: reuse one conversation_id across multiple runs and across two agents.
#
# Creates two agents with distinct personas (a Geography expert and a Math expert),
# creates ONE conversation, then alternates turns between the two agents using the
# same conversation_id so that each agent can see the full prior history written by
# the other.
#
# Run:
#     python shared_conversation_demo.py
#
# Required env vars:
#     AZURE_AI_PROJECT_ENDPOINT          e.g. https://<account>.services.ai.azure.com/api/projects/<project>
#     AZURE_AI_MODEL_DEPLOYMENT_NAME     e.g. gpt-4o
#
# Optional:
#     KEEP_RESOURCES=1                   keep the agents + conversation after the run
#                                        (default is to delete them)
# ------------------------------------

import os
import time
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition

load_dotenv()

endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
model = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
keep_resources = os.environ.get("KEEP_RESOURCES") == "1"


def hr(title: str) -> None:
    print()
    print("=" * 78)
    print(f" {title}")
    print("=" * 78)


def run_turn(openai_client, conversation_id: str, agent_name: str, user_text: str) -> str:
    """Append a user message then ask the named agent to respond on the shared conversation."""
    openai_client.conversations.items.create(
        conversation_id=conversation_id,
        items=[{"type": "message", "role": "user", "content": user_text}],
    )
    response = openai_client.responses.create(
        conversation=conversation_id,
        extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}},
        input="",
    )
    print(f"\n[{agent_name}] user: {user_text}")
    print(f"[{agent_name}] assistant: {response.output_text}")
    print(f"[{agent_name}] response.id={response.id}  conv={conversation_id}")
    return response.id


with (
    DefaultAzureCredential() as credential,
    AIProjectClient(endpoint=endpoint, credential=credential) as project_client,
    project_client.get_openai_client() as openai_client,
):

    hr("1. Create two agents with distinct personas")

    geo_agent = project_client.agents.create_version(
        agent_name="FoundryNew-GeoAgent",
        definition=PromptAgentDefinition(
            model=model,
            instructions=(
                "You are a geography expert. Answer only geography questions concisely. "
                "If asked anything outside geography, say 'That's outside my area; ask the math agent.'"
            ),
        ),
    )
    print(f"Geo agent  -> id={geo_agent.id}  name={geo_agent.name}  version={geo_agent.version}")

    math_agent = project_client.agents.create_version(
        agent_name="FoundryNew-MathAgent",
        definition=PromptAgentDefinition(
            model=model,
            instructions=(
                "You are a math expert. Answer only math/calculation questions concisely. "
                "If asked anything outside math, say 'That's outside my area; ask the geo agent.'"
            ),
        ),
    )
    print(f"Math agent -> id={math_agent.id}  name={math_agent.name}  version={math_agent.version}")

    hr("2. Create ONE conversation (both agents will share it)")

    conversation = openai_client.conversations.create(items=[])
    conv_id = conversation.id
    print(f"conversation_id = {conv_id}")

    hr("3. Run multiple turns alternating between the two agents")

    # Turn 1 - Geo agent answers a geography question.
    run_turn(openai_client, conv_id, geo_agent.name,
             "What is the capital of France and roughly how many people live there?")

    # Turn 2 - Math agent on the SAME conversation. It should SEE turn 1 in history.
    run_turn(openai_client, conv_id, math_agent.name,
             "Given the population you just heard from the geo agent, "
             "if 18% commute by metro, approximately how many metro commuters is that?")

    # Turn 3 - Back to Geo agent, referencing the math answer.
    run_turn(openai_client, conv_id, geo_agent.name,
             "Name two other major cities in the same country, and tell me which one is closest to the capital.")

    # Turn 4 - Math agent again, building on everything above.
    run_turn(openai_client, conv_id, math_agent.name,
             "If the closest of those two cities is about 130 km from the capital "
             "and a train averages 220 km/h, how many minutes is the journey?")

    # Turn 5 - Cross-check: ask the Geo agent something only answerable from the math agent's prior reply.
    run_turn(openai_client, conv_id, geo_agent.name,
             "Earlier the math agent gave a journey time in minutes. Repeat that number back to confirm "
             "you can see it in the shared conversation.")

    hr("4. Dump the full conversation as stored server-side")

    items = openai_client.conversations.items.list(conversation_id=conv_id)
    for i, item in enumerate(items, start=1):
        kind = getattr(item, "type", "?")
        role = getattr(item, "role", "")
        if kind == "message":
            content_parts = getattr(item, "content", []) or []
            text_chunks = []
            for c in content_parts:
                t = getattr(c, "text", None)
                if t is None and isinstance(c, dict):
                    t = c.get("text")
                if t:
                    text_chunks.append(t if isinstance(t, str) else getattr(t, "value", str(t)))
            text = " ".join(text_chunks).strip()
            preview = (text[:140] + "…") if len(text) > 140 else text
            print(f"{i:>2}. [{role:>9}] {preview}")
        else:
            print(f"{i:>2}. [{kind}] id={getattr(item, 'id', '?')}")

    hr("5. What you should now see in BYO Cosmos")
    print(f"DB        : enterprise_memory")
    print(f"Container : <project-internalId>-run-state-v1")
    print(f"Look for  : conv_{conv_id.split('_', 1)[-1]} and the matching resp_/msg_ docs.")
    print(f"Edges     : FoundryNew-GeoAgent_*_conv_{conv_id.split('_', 1)[-1]}")
    print(f"            FoundryNew-MathAgent_*_conv_{conv_id.split('_', 1)[-1]}")
    print(f"            (one edge per (agent, version) that touched the conversation)")

    if not keep_resources:
        hr("6. Cleanup (set KEEP_RESOURCES=1 to skip)")
        try:
            openai_client.conversations.delete(conversation_id=conv_id)
            print(f"Deleted conversation {conv_id}")
        except Exception as e:
            print(f"Conversation delete failed: {e}")
        for a in (geo_agent, math_agent):
            try:
                project_client.agents.delete_version(agent_name=a.name, agent_version=a.version)
                print(f"Deleted agent {a.name} v{a.version}")
            except Exception as e:
                print(f"Agent delete failed for {a.name}: {e}")
    else:
        print("\nKEEP_RESOURCES=1 set -> leaving agents and conversation in place.")
        print(f"  conversation_id = {conv_id}")
        print(f"  geo_agent       = {geo_agent.name} v{geo_agent.version}")
        print(f"  math_agent      = {math_agent.name} v{math_agent.version}")
