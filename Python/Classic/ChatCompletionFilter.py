import json
import httpx
from azure.identity import DefaultAzureCredential

endpoint = "https://mfbr-ext-eus2-aiml-profx-01.services.ai.azure.com"
model = "gpt-4.1-CF"

# Get a token using DefaultAzureCredential
credential = DefaultAzureCredential()
token = credential.get_token("https://cognitiveservices.azure.com/.default").token

# Call the chat completions endpoint directly via HTTP to get the full raw response
url = f"{endpoint}/openai/deployments/{model}/chat/completions?api-version=2024-12-01-preview"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

system_prompt = """# Productivity Plan Configuration Task Prompt
## Role
**Agent Name**: myISP_Get_ProductivityDetailsForStaffing
**Role**: Fetch or configure productivity percentages/schedules for staffing
## CRITICAL TRIGGER CONDITIONS:
**ONLY CALL THIS AGENT WHEN:**
- When user prompt has the context of Staffing productivity
**DO NOT CALL THIS AGENT FOR:**
- "Gen AI productivity", "GenAI productivity", "genai productivity" (without "staffing")
- "AM productivity", "AD productivity" in Gen AI context (e.g., "AM genai productivity has 25% improvement")
- Any productivity mentions related to Gen AI, AI improvements, or AI benefits
- General productivity improvements that don't explicitly reference staffing
- When user prompt has the context of only Gen AI productivity but not the Staffing Productivity → DO NOT call this agent
**MANDATORY RULES**:
- **Data to Ignore**: group counts, profile details, FTE, ramp-up schedules, cost amounts, pricing configurations,"AM","AD" % splits given in the context of group creation.
- **NEVER ask user for clarification**: When uncertain about any data → Ask: "Does this data control MY specific action?" If NO → IGNORE it and proceed autonomously.
- **Error**: Context Not Allowed – Actions [Delete, Import, Export, Activate/Deactivate, Copy, Rename] are restricted for entity: Get Productivity Details for Staffing.
## Glossary
- ProductivityPercent: Integer 0-100 applied at interval or schedule month
- ProductivitySchedule: Object mapping "M<month>" to percent
- ServiceTypes: ["AD", "AM", "Testing"]
- DealDuration: Integer >0 total contract months
## Execution Rules
- Fully automated - NO user prompts or confirmations
- Stop immediately on any validation failure
- NO retries needed (no MCP calls)
- Total API calls = 0 (Custom_Productivity formed directly from user input)
- Return failure with specific error message if validation fails
## Error Handling (Applies to ALL Steps)
**Immediate Failure Conditions:**
- Missing/empty groups_List or invalid group object
- Duplicate SolutionGroupId entries
- Invalid DealDuration (≤0)
- No groups found (count = 0)
- Ambiguous input (conflicting triggers)
- Group name not found in matching
- ServiceType not found
- API call failure, timeout (>15s), or invalid JSON response
- Missing output group in Custom_Productivity
- Invalid productivity values (<0 or >100)
- **Cumulative productivity exceeds 100% for any group** (sum of all month percentages >100)
**On Any Failure:**
1. Stop execution immediately
2. Return specific error message
3. Output failure response:
```json
{
  "agentName": "myISP_Get_ProductivityDetailsForStaffing",
  "agentResponse": "[Specific error description]",
  "agentStatus": "Failure"
}
```
---
## Process Steps
### Step 1: Validate Input
**CRITICAL SKIP LOGIC (Execute FIRST before any other validation)**:
1. Check user input for Gen AI productivity context WITHOUT staffing:
   - Contains "Gen AI productivity", "GenAI productivity", "genai productivity"
   - Contains "AM genai productivity", "AD genai productivity"
   - Contains "Gen AI screen", "save Gen AI screen", "Gen AI embedded"
   - Contains "Gen AI improvement", "AI improvement" with productivity
   - Contains "Gen AI solution" with productivity mentions
2. Check for staffing productivity context:
   - Does NOT contain "staffing productivity" AND does NOT contain "productivity for staffing"
**If Gen AI productivity indicators found AND NO "staffing productivity" mentioned**:
→ **IMMEDIATELY SKIP and return**:
```json
{
  "agentName": "myISP_Get_ProductivityDetailsForStaffing",
  "agentResponse": "Skipped - productivity mentioned in Gen AI context, not staffing productivity. This agent only handles staffing productivity plans.",
  "agentStatus": "Skip"
}
```
**Pre-execution Validation**:
**Fetch groups_List from myISP_GetGroup_tool Results**:
- Extract groups_List from the results of myISP_GetGroup_tool (executed in myISP_Get_GroupDetailsForStaffing)
- Expected structure: Array with objects containing SolutionGroupId, SolutionGroupNm, ServiceTypeNm, IsActive
- Filter: Keep only IsActive = true groups
- If groups_List is empty or missing → **STOP and RETURN FAILURE: "No active groups found from myISP_GetGroup_tool results"**
- If groups_List is missing → **STOP and RETURN FAILURE: "groups_List is required"**
- If groups_List is empty → **STOP and RETURN FAILURE: "groups_List cannot be empty"**
- If DealDuration is missing → **STOP and RETURN FAILURE: "DealDuration is required"**
- If DealDuration ≤0 → **STOP and RETURN FAILURE: "DealDuration must be positive integer"**
- All parameters valid → Proceed to Step 2
**Validate groups_List fields**:
- Each entry must have: SolutionGroupId (integer >0), SolutionGroupNm (non-empty), ServiceTypeNm (["AD","AM","Testing"])
- If validation fails → **STOP and RETURN FAILURE: "Invalid group object in groups_List"**
### Step 2: Extract Group Information
Capture from groups_List: SolutionGroupId, SolutionGroupNm, ServiceTypeNm
If zero groups found → **STOP and RETURN FAILURE: "No groups found"**
### Step 3: Select Allocation Strategy
**Check in exact order, use first match**:
#### a. Default Group Allocation
**Trigger**: Input contains "per group" OR "for all groups" OR "each group" WITHOUT group names or service-type tokens
**Logic**: Apply same productivity plan to all groups from groups_List
#### b. Direct Group Name Matching
**Trigger**: Input contains group names
**Matching Algorithm**:
- Split user input by spaces/commas/semicolons
- For each token, check if SolutionGroupNm contains token (case-insensitive)
- If multiple groups match single token → **STOP and RETURN FAILURE: "Ambiguous group name"**
- If no groups match → **STOP and RETURN FAILURE: "Group name not found"**
- Apply productivity plan to each matched group
#### c. Service Type-Based Allocation
**Trigger**: Input contains service-type tokens (["AD", "AM", "Testing"])
**Logic**: Match ServiceTypeNm exactly, apply plan to all matched groups
### Step 4: Build Productivity JSON
**Extraction Algorithm**:
1. Extract numeric values from user input
2. Check if number appears within 10 words of keywords: "productivity", "efficiency", "percent", "%", "improvement"
3. **Extract starting month**:
   - Check for explicit month specifications: "M<number>", "month <number>", "starting from month X", "from month X", "begin at month X"
   - Examples: "M3 - 5%", "month 5", "starting from month 3"
   - If no explicit starting month → Default to M1 for initial ranges, or interval duration for recurring patterns
4. **Extract interval patterns**:
   - Check for "every X months", "each X months", "per X months"
   - Check for named intervals:
     * "half yearly" or "half-yearly" or "semi-annually" → 6 months
     * "yearly" or "annual" or "annually" → 12 months
     * "quarterly" → 3 months
     * "biannual" or "bi-annual" → 6 months
5. Extract duration: Check for numbers followed by "months", "month", or named numbers {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
6. Extract schedule: Check for "M<number>" or "month <number>" patterns with associated percentages
7. **Extract multi-phase productivity patterns**:
   - Pattern A: "Months X-Y: Z%" → Initial productivity ranges
   - Pattern B: "Increase by X% every Y months" → Incremental recurring pattern
   - Pattern C: "Group - M<number> - X%" → Single month with percentage
   - Pattern D: "Group - interval X%" → Simple recurring pattern
   - When both patterns exist: Apply Pattern A for initial periods, then apply Pattern B starting after the last month of Pattern A
**CRITICAL - Productivity Output Format Rules**:
- **Starting month detection**: ALWAYS check user input for explicit month specifications
- **For initial productivity ranges**: Output the starting month of each range with its percentage value
- **For recurring intervals without initial ranges**: First occurrence starts at the interval duration itself
- **For recurring intervals after initial ranges**: Calculate first interval occurrence after the last initial range
- **For recurring intervals after explicit starting month**: Calculate first interval occurrence: starting_month + interval
- **For recurring intervals**: Output ONLY the incremental change value at each interval month
- **MonthlyData format**: Include ONLY months where productivity changes occur
- **Continue intervals until DealDuration**: Generate interval entries up to the total deal duration
### Step 5: Form Custom_Productivity Directly from User Input
**IMPORTANT**: Do NOT call any MCP tool. Directly construct Custom_Productivity JSON based on user input and Step 4 extraction.
### Step 6: Construct Output JSON
Always return logical reasoning for the below Json creation and always show this Agent results
**Validation Before Output**:
- Include only non-zero values (1-100)
- Keys format "M<month>" ascending, no duplicates
- All requested groups must be present
- If group missing → **STOP and RETURN FAILURE: "Missing group in Custom_Productivity"**
- **CRITICAL - Cumulative Validation**: For EACH group in Custom_Productivity output:
  * Calculate sum of all values in MonthlyData
  * If sum >100 for ANY group → **STOP and RETURN FAILURE**
### Step 7: Return Completion
Return response in exact JSON format with agentName, agentResponse, agentStatus
**Total API Calls:** 0 (No MCP calls - Custom_Productivity formed directly from user input)
"""

user_prompt = """Create a new version with the following configuration: Start Date: June 1st 2026 , End Date: May 30th 2029 Currency: USD Consider Onshore as USA with 100% and Offshore as India with 100% Apply Onshore Offshore guideline as 20%:80% Group Configuration: Create 2 groups with: 1 group called as AM , which includes Skill Tier 1 and 1 group called as AD with Skill Tier 2 Apply skill mix with: ERP 70% weightage of Pyramid and Custom 30% weightage of Pyramid Staffing Plan Options: Create LBS based staffing with Peak FTE as 100 in each group. Transition start with Month 1: 25 FTEs, Month 2: 50 FTEs, Month 3: 75 FTEs and Month 4: 100 FTEs for each group. Service Delivery starts from 5th Month Please apply Cumulative Productivity as below for both groups: Month 1:0%, Month 13: 10%, Month 25: 16%, Month 31: 25% Additional Costs: Add $50000 Travel Cost for Transition and Service Delivery for All Profiles and all Groups. Consider PMO Tax at 5% Gen AI is embedded for AM and AD. AM has 25% productivity improvement, AD has 35% improvement. solution is GenWizard, AD solution is GenWizard. AM benefit is productivity gain, AD benefit is cost reduction. AM followed AMS guidelines, AD followed AMS Gen AI guidelines. cost is included. SME: b.chandran.pillai and included cost is 10000 Once the version is created, generate the OCP."""

# Chat history from prior agent executions (simulating orchestration context)
chat_history = [
    {"role": "user", "content": user_prompt},
    # Orchestrator classification response
    {"role": "assistant", "content": """Action: Create Version and Group and Staffing and Infra and OtherCost and PMO and GenAI and OCP
Qualifiers: in each group. transition start with; for each group. service delivery starts; from 5th month please apply cumulative; for both groups: month 1:0%, month; for transition and service delivery; for all profiles and all groups.; at 5% gen ai is embedded; for am and ad. am has
Modifiers: with the following configuration: start date: june 1st 2026 , end date: may 30th 2029 currency: usd consider onshore as usa with 100% and offshore as india with 100% apply onshore offshore guideline as 20%:80% group configuration: create 2 groups with: 1 group called as am , which includes skill tier 1 and 1 group called as ad with skill tier 2 apply skill mix with: erp 70% weightage of pyramid and custom 30% weightage of pyramid staffing plan options: create lbs based staffing with peak fte as 100 in each group; 25% additional; 5% gen; 25% productivity; 35% improvement
AgentList: [{"Sequence": 1, "TaskName": "Validate_User"},{"Sequence": 2, "TaskName": "Get_OpportunityDetails"},{"Sequence": 3, "TaskName": "Create_SolutionVersion"},{"Sequence": 4, "TaskName": "Lock_SolutionVersion"},{"Sequence": 5, "TaskName": "Save_GroupDetail"},{"Sequence": 6, "TaskName": "Get_GroupDetailsForStaffing"},{"Sequence": 7, "TaskName": "Get_RampUpForStaffing"},{"Sequence": 8, "TaskName": "Get_ProductivityDetailsForStaffing"},{"Sequence": 9, "TaskName": "Get_GuidanceDetailsForStaffing"},{"Sequence": 10, "TaskName": "Save_Staffing"},{"Sequence": 11, "TaskName": "Save_mobilization"},{"Sequence": 12, "TaskName": "Save_PMOandTAXCost"},{"Sequence": 13, "TaskName": "Save_OtherCost"},{"Sequence": 14, "TaskName": "Save_InfraCost"},{"Sequence": 15, "TaskName": "Save_GenAI"},{"Sequence": 16, "TaskName": "Save_TaxCost"},{"Sequence": 17, "TaskName": "UnLock_SolutionVersion"},{"Sequence": 18, "TaskName": "Generate_OCP"},{"Sequence": 19, "TaskName": "Generate_OutputSummary"}]"""},
    # Validate_User result
    {"role": "assistant", "content": '{"agentName": "Validate_User_Agent", "agentResponse": "User authorized as Solution Architect", "agentStatus": "Success"}'},
    # Get_OpportunityDetails result
    {"role": "assistant", "content": '{"agentName": "Get_OpportunityDetails", "agentResponse": "solutionId: 39299, opportunityId: 1604076", "agentStatus": "Success"}'},
    # Create_SolutionVersion result
    {"role": "assistant", "content": '{"agentName": "Solution_Version_Creation_Agent", "agentStatus": "Success", "versionId": 201713, "versionNumber": "330.0", "startDate": "06/01/2026", "endDate": "05/30/2029", "eligibilityResult": {"isEligible": true, "dealDurationMonths": 36}, "productivityAssessmentCreated": true}'},
    # Lock_SolutionVersion result
    {"role": "assistant", "content": '{"agentName": "Lock_Unlock_Solution_Version", "agentResponse": "Version has been locked successfully.", "agentStatus": "Success", "details": {"versionNumber": "", "isLocked": true, "lockedBy": "kunal.ramdas.bhade"}}'},
    # Save_GroupDetail result
    {"role": "assistant", "content": '{"agentName": "myIsP_Save_GroupDetail", "agentResponse": "Group details saved successfully. Total groups created: 2", "agentStatus": "Success"}'},
    # Get_GroupDetailsForStaffing result (contains groups_List)
    {"role": "assistant", "content": """Step 1: Retrieve Groups
Active groups found:
AM (solutionGroupId: 1305047, serviceTypeNm: AM)
AD (solutionGroupId: 1305048, serviceTypeNm: AD)

Step 2: Parse User Intent & Dynamic Extraction
FTE Extraction: Peak FTE as 100 in each group → Both AM and AD get 100 FTE
NoofSDMonths: Service Delivery starts from 5th Month → NoofSDMonths = 5

Step 4: Build Output
Output 1:
{"groups": [{"SolutionGroupId": 1305047, "FTE": 100, "NoofSDMonths": 5}, {"SolutionGroupId": 1305048, "FTE": 100, "NoofSDMonths": 5}]}

Output 2:
{"groups_List": [{"SolutionGroupId": 1305047, "SolutionGroupNm": "AM", "ServiceTypeNm": "AM"}, {"SolutionGroupId": 1305048, "SolutionGroupNm": "AD", "ServiceTypeNm": "AD"}]}

{"agentName": "myISP_Get_GroupDetailsForStaffing", "agentResponse": "FTE distribution plan completed", "agentStatus": "Success"}"""},
    # Get_RampUpForStaffing result
    {"role": "assistant", "content": """{"agentName": "myISP_Get_RampUpForStaffing", "agentResponse": "Transition (Ramp-up) plan completed", "agentStatus": "Success"}

Logical Reasoning:
- Operation Type: INSERT (user requested "create" for transition/ramp-up).
- Group matching: All active groups (AM and AD) included.
- Duration extraction: Explicit transition for 4 months.
- Percentages applied: [25, 50, 75, 100] for both groups.

Output JSON:
{"groupTransitions": {"AM": {"solution_group_id": 1305047, "transition_months": 4, "rampup_percentages": [25, 50, 75, 100], "start_month": 1}, "AD": {"solution_group_id": 1305048, "transition_months": 4, "rampup_percentages": [25, 50, 75, 100], "start_month": 1}}}"""},
]

payload = {
    "messages": [
        {"role": "system", "content": system_prompt},
        *chat_history,
        # Now the orchestrator hands off to Get_ProductivityDetailsForStaffing
        {"role": "user", "content": "Execution completed for agent:myISP_Get_RampUpForStaffing. Execution in progress for agent:myISP_Get_ProductivityDetailsForStaffing. Process the productivity details from the user request using the groups_List and DealDuration from prior agent results."}
    ],
    "temperature": 0.2
}

# Run multiple times with non-streaming to check consistency
for run in range(1, 21):
    print(f"\n{'='*60}")
    print(f"RUN {run}")
    print(f"{'='*60}")

    response = httpx.post(url, headers=headers, json=payload, timeout=60)
    body = response.json()

    choice = body["choices"][0]
    finish = choice.get("finish_reason", "unknown")
    content = choice.get("message", {}).get("content", "")
    cfr = choice.get("content_filter_results", {})

    # Check which filter triggered
    blocked_by = []
    for key, val in cfr.items():
        if isinstance(val, dict) and val.get("filtered", False):
            blocked_by.append(f"{key}: {val}")
        elif isinstance(val, dict) and "details" in val:
            for detail in val.get("details", []):
                if detail.get("filtered", False):
                    blocked_by.append(f"{key}/{detail.get('id', '?')}")
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict) and item.get("filtered", False):
                    blocked_by.append(f"{key}/{item.get('id', '?')}")

    tokens = body.get("usage", {}).get("completion_tokens", 0)

    print(f"  Finish: {finish}")
    print(f"  Completion tokens: {tokens}")
    print(f"  Content Filter Results: {json.dumps(cfr, indent=4)}")
    if blocked_by:
        print(f"  *** BLOCKED BY: {', '.join(blocked_by)}")
    else:
        print(f"  Filter: PASSED")
    if content:
        print(f"\n  === Full Agent Response ===")
        print(content)
    else:
        print(f"  Content: (empty - filtered)")

print("\n\nDone.")
