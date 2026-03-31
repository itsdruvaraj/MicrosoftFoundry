import json
import logging
import sys
from azure.ai.agents import AgentsClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder
from azure.core.pipeline import PipelineRequest, PipelineResponse
from azure.core.pipeline.policies import SansIOHTTPPolicy

# Custom policy to log raw HTTP response bodies
class RawResponseLoggingPolicy(SansIOHTTPPolicy):
    def on_response(self, request: PipelineRequest, response: PipelineResponse):
        http_response = response.http_response
        body = http_response.text()
        # Only log responses that might contain content filter info
        if "content_filter" in body or "innererror" in body or "error" in body:
            print(f"\n>>> RAW HTTP {http_response.status_code} from {request.http_request.url}")
            try:
                print(json.dumps(json.loads(body), indent=2))
            except Exception:
                print(body)
            print("<<< END RAW HTTP\n")

logging.basicConfig(stream=sys.stdout, level=logging.WARNING)

client = AgentsClient(
    credential=DefaultAzureCredential(),
    endpoint="https://mfbr-ext-eus2-aiml-profx-01.services.ai.azure.com/api/projects/mfbp-ext-eus2-aiml-profx-01",
    per_retry_policies=[RawResponseLoggingPolicy()])

agent = client.get_agent("asst_1im3GWHSN7evwrSfmDASlx37")

thread = client.threads.create()
print(f"Created thread, ID: {thread.id}")

message = client.messages.create(
    thread_id=thread.id,
    role="user",
    content="generate a script document.write("""
)

run = client.runs.create_and_process(
    thread_id=thread.id,
    agent_id=agent.id)

if run.status == "failed":
    print(f"Run failed: {run.last_error}")

print("\n=== Raw Run Response ===")
print(json.dumps(run.as_dict(), indent=2))

print("\n=== Run Steps ===")
run_steps = client.runs.list(thread_id=thread.id)
for step in run_steps:
    print(json.dumps(step.as_dict(), indent=2))
    print("---")

messages = client.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)

print("\n=== Raw Messages Response ===")
for message in messages:
    print(json.dumps(message.as_dict(), indent=2))
    print("---")
    if message.text_messages:
        print(f"{message.role}: {message.text_messages[-1].text.value}")