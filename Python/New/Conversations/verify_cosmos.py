# ------------------------------------
# Reads BYO Cosmos directly to prove the demo's shared-conversation behaviour:
#   - all 5 resp_ docs sit on the same conversation partition
#   - both agents' (agent -> conv) edges live in their own per-agent partitions
#   - input-token count grows turn over turn (history is being hydrated)
#
# Run AFTER shared_conversation_demo.py with KEEP_RESOURCES=1, paste the
# printed conversation_id into CONV below.
#
# Requires:  pip install azure-cosmos azure-identity
# Required role on the Cosmos account (your signed-in user):
#   "Cosmos DB Built-in Data Reader"  (00000000-0000-0000-0000-000000000001)
# ------------------------------------

from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

ENDPOINT = "https://nosql-ext-eus2-mfstd-profx-02.documents.azure.com:443/"
DB = "enterprise_memory"
CTR = "91203f3d-32e7-4dfd-8a15-12c4918a3898-run-state-v1"
ACCOUNT_PROJECT_PREFIX = "aisrvs-eus2-mfstd-02fxwl@proj-eus2-mfstd-02fxwl@AML"

# Paste from the demo script's final summary:
CONV = "conv_4a5745f24caece0d00EPO3FGkFopYg9SMwulaSty6ad8sIGOz1"
AGENTS = ("FoundryNew-GeoAgent", "FoundryNew-MathAgent")


def derive_pk_from_conv(conv_id: str) -> str:
    # Format: conv_<18hexHash><originalSuffix> -> partition_id is the 18-hex hash
    suffix = conv_id.split("_", 1)[1]
    return f"{ACCOUNT_PROJECT_PREFIX}/{suffix[:18]}"


pk_conv = derive_pk_from_conv(CONV)
client = CosmosClient(ENDPOINT, credential=DefaultAzureCredential())
ctr = client.get_database_client(DB).get_container_client(CTR)

print(f"conversation : {CONV}")
print(f"partition_id : {pk_conv}\n")

print("=== Turns (resp_) in order — proves history is shared & tokens grow ===")
turns = list(ctr.query_items(
    query=(
        "SELECT c.id, c.object.agent.name AS agent, c.object.agent.version AS ver, "
        "c.object.usage.input_tokens AS in_t, c.object.usage.output_tokens AS out_t "
        "FROM c WHERE STARTSWITH(c.id, 'resp_') "
        f"AND c.object.conversation.id = '{CONV}' ORDER BY c._ts ASC"
    ),
    partition_key=pk_conv,
))
for i, r in enumerate(turns, 1):
    print(f"  Turn {i}: {r['agent']:>22} v{r['ver']}  tokens in={r['in_t']:>5} out={r['out_t']:>4}")

print(f"\nTotal turns: {len(turns)}    Distinct agents: {sorted(set(t['agent'] for t in turns))}")

print("\n=== Doc-type breakdown on the conversation partition ===")
counts = {}
for r in ctr.query_items(query="SELECT c.id FROM c", partition_key=pk_conv):
    prefix = r["id"].split("_", 1)[0]
    counts[prefix] = counts.get(prefix, 0) + 1
for k, v in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {k:>14}_ : {v}")

print("\n=== Agent -> conversation edges (separate per-agent partitions) ===")
conv_suffix = CONV.split("_", 1)[1][18:]  # the original-suffix part after the 18-hex hash
for agent in AGENTS:
    pk_agent = f"{ACCOUNT_PROJECT_PREFIX}/{agent}"
    for r in ctr.query_items(
        query="SELECT c.id FROM c WHERE c.object.object_type = 'edge.agent2conversation'",
        partition_key=pk_agent,
    ):
        if r["id"].endswith(conv_suffix):
            print(f"  partition=…/{agent}")
            print(f"     edge id : {r['id']}")
