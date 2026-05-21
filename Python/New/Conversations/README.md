# Shared Conversation across two agents

Demonstrates that in Microsoft Foundry (v2 / Responses-API agents) a single
`conversation_id` can be reused across multiple runs **and across different
agents**, with each new call seeing the full prior history.

## What it does

1. Creates two agents with distinct personas:
   - `FoundryNew-GeoAgent` – geography expert
   - `FoundryNew-MathAgent` – math expert
2. Creates ONE conversation.
3. Runs 5 turns, alternating which agent responds, where each later turn
   deliberately depends on something a different agent said earlier.
4. Lists the full server-side conversation items so you can see the
   interleaved transcript.
5. Cleans up (unless `KEEP_RESOURCES=1`).

## Run

```powershell
cd C:\local\git\Personal\microsoftfoundry\Python\New\Conversations

pip install "azure-ai-projects>=2.0.0b1" python-dotenv openai

$env:AZURE_AI_PROJECT_ENDPOINT  = "https://aisrvs-eus2-mfstd-02fxwl.services.ai.azure.com/api/projects/proj-eus2-mfstd-02fxwl"
$env:AZURE_AI_MODEL_DEPLOYMENT_NAME = "gpt-4o"      # or whichever deployment you have

# Sign in once for DefaultAzureCredential
az login

python shared_conversation_demo.py
```

Set `KEEP_RESOURCES=1` if you want to inspect the agents/conversation in
the portal or Cosmos afterwards instead of cleaning up.

## Verified results from a real run

A demo run produced this in the BYO Cosmos `…run-state-v1` container (verified
via `verify_cosmos.py`):

```
conversation : conv_14d534941fd12c60000c69J8wDRwQyoeaAeh8H2dJ4zKhM5UJL
partition_id : …@AML/14d534941fd12c6000

Turns in order (history shared across agents — input_tokens grow each turn):
  Turn 1:    FoundryNew-GeoAgent v1  tokens in=   57 out=  25
  Turn 2:   FoundryNew-MathAgent v1  tokens in=  118 out=  40
  Turn 3:    FoundryNew-GeoAgent v1  tokens in=  184 out=  43
  Turn 4:   FoundryNew-MathAgent v1  tokens in=  267 out=  90
  Turn 5:    FoundryNew-GeoAgent v1  tokens in=  388 out=  11

Doc-type breakdown on the conv partition:
  msg_       : 10   (5 user + 5 assistant)
  item2conv_ : 10   (one reverse-index doc per item)
  resp_      :  5   (one per turn)
  conv_      :  1   (conversation root)
  conv2item_ :  1   (forward index, _0 page only — well under 2 MB)

Agent -> conversation edges (each in its OWN partition):
  …@AML/FoundryNew-GeoAgent   -> FoundryNew-GeoAgent_1_conv_0c69J…
  …@AML/FoundryNew-MathAgent  -> FoundryNew-MathAgent_1_conv_0c69J…
```

Two behaviours worth noting:

- **History IS shared.** Turn 2 (Math) correctly used the 2.1 M population
  Turn 1 (Geo) produced (→ 378,000 commuters). Turn 4 (Math) correctly used
  the city "Lyon" that Turn 3 (Geo) named. `input_tokens` climbs from 57 to
  388 — clear evidence that prior turns are hydrated into context on every
  call.
- **Per-agent behaviour is preserved.** Turn 5 asked the Geo agent to repeat
  a number the Math agent had produced. The history was visible to it, but its
  system instructions say *"If asked anything outside geography, refuse."* —
  and it replied **"That's outside my area; ask the math agent."** This is
  exactly the design: history is shared, behaviour is per-agent.

## What to look for in Cosmos

In `nosql-ext-eus2-mfstd-profx-02 / enterprise_memory /
<projectInternalId>-run-state-v1` (partition key = `/partition_id`):

- 1 × `conv_<id>` (the shared conversation root)
- 5 × `resp_<id>` (one per turn) – each carries `agent.{name,version}` and
  the same `conversation.id`
- 10 × `msg_<id>` (5 user + 5 assistant)
- 1+ × `conv2item_<convId>_<page>` (ordered index of all items)
- `item2conv_<itemId>_0` per item (reverse index)
- 2 × `<agentName>_<version>_conv_<convId>` edge docs – one per agent that
  touched the conversation, sitting in their own per-agent partitions.

Query in Data Explorer (replace partition key in toolbar with the
conversation's derived partition value, e.g. `…@AML/<convHash>`):

```sql
-- All turns of this conversation, in order, with the agent that handled each
SELECT c.id AS resp_id,
       c.object.agent.name      AS agent,
       c.object.agent.version   AS ver,
       c.object.usage.input_tokens,
       c.object.usage.output_tokens,
       c._ts
FROM c
WHERE STARTSWITH(c.id, 'resp_')
  AND c.object.conversation.id = '<paste conversation_id here>'
ORDER BY c._ts ASC
```

Expected result: 5 rows, agents alternating between `FoundryNew-GeoAgent`
and `FoundryNew-MathAgent`, all sharing the same `conversation.id`.
