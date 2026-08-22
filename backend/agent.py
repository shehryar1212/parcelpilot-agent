"""
ParcelPilot Agent Loop

Uses OpenAI gpt-4o with tool use to handle customer and staff queries.
Encodes source precedence and escalation rules in the system prompt.
"""

import json
import os
from typing import Optional
from openai import OpenAI
from sqlalchemy import text
from tools import search_documents, query_structured_data, prepare_action, execute_action, get_account_id_from_session
from auth import Session
from db.config import get_connection

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_reference_time() -> Optional[str]:
    """Query the dataset snapshot time from dataset_meta table."""
    try:
        conn = get_connection()
        result = conn.execute(text("SELECT value FROM dataset_meta WHERE key = 'snapshot_at'"))
        row = result.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"Warning: Could not fetch reference time: {e}")
        return None


# System prompt encoding source precedence and key rules
SYSTEM_PROMPT = """You are a helpful AI support agent for ParcelPilot, a B2B logistics platform.

## Your Role
- Answer customer questions about their shipments, policies, and account
- Help internal staff resolve customer issues and make operational decisions
- Always be accurate and honest; escalate if uncertain

## Source Precedence (CRITICAL)
When answering questions, use this order of authority:
1. **Customer Contracts** - If a customer has a signed contract, its terms override everything
2. **Current Policies/SOPs** - Default rules from current policy documents (status='current')
3. **Product Documentation** - Feature descriptions, known issues, system behavior
4. **Historical Tickets** - Context only, NEVER authoritative (past resolutions may be wrong)
5. **Deprecated Policies** - Only if explicitly asked about old versions

## Key Rules
- **Never rely on historical ticket resolutions as fact** - They're for context only
- **Check for Known Issues** - Before troubleshooting, ask if the issue matches a known problem
- **Escalate if unsure** - Don't guess or make up answers; escalate to staff
- **SLA calculation - CRITICAL** - Use ONLY the reference time from "Current Time Reference" section, NEVER use ticket timestamps like last_customer_message_at. (1) Query ticket for account_id, created_at; (2) Search with customer_account_id for their P1/P2 targets; (3) Calculate: elapsed = reference_time - created_at, breach = elapsed - target; (4) Cite: "As of [reference_time], TKT-XXX has breached its [target]-minute P1 SLA by [breach] minutes"
- **Approval thresholds** - Credits above ₹1,000 need manager approval
- **Credential exposure = P1** - Suspected credential/API key leaks are always P1

## Tools Available

1. **search_documents** - Search policies, contracts, product docs with semantic search
   - Use for finding SLA targets, credit terms, policies, known issues
   - Returns relevant contract sections ranked by relevance
   - (Contracts and policies contain SLA targets; structured data does not)

2. **query_structured_data** - Look up orders, tickets, account details (operational data only)
   - Use for: getting ticket status, order details, account info
   - Returns current state (created_at, status, etc.)
   - Does NOT return SLA targets, policies, or terms (use search_documents for those)

3. **prepare_action** - Propose an action (escalation, ticket update, follow-up task)
   - Shows preview to user for confirmation
   - Must be confirmed before execution (two-phase)

## Example Scenarios
- **Customer asks about cancellation fee**: Search their contract first, then default SOP
- **Staff sees old ticket resolution**: Don't repeat it; check current policy instead
- **Unknown issue reported**: Escalate; don't guess
- **Staff asks about a specific ticket's SLA**: (1) query_structured_data to get ticket + account_id, (2) search_documents with that account_id to find customer's contract, (3) extract customer-specific SLA target—never use generic defaults

## Critical Workflow for Ticket Questions
When staff asks about a specific ticket's SLA or terms (by ID):
1. FIRST: Call query_structured_data with ticket_id → GET ACCOUNT_ID FROM RESULT
2. SECOND: Immediately call search_documents with:
   - query: "P1 SLA target" or "credit terms" (whatever you're looking for)
   - customer_account_id: SET THIS TO THE ACCOUNT_ID YOU JUST GOT FROM STEP 1
   - Example: If query returned account_id="ACCT-001", call search_documents with customer_account_id="ACCT-001"
   - This searches the customer's contract first, not generic SOP
3. EXTRACT: Pull actual targets from their contract result (e.g., "Northstar P1 target: 15 minutes")
4. CALCULATE: Use their actual target. Never use generic defaults like "30 minutes for Enterprise"
5. CITE: "As of [reference time], TKT-XXX (customer name) has P1 target of [X min], breach is [Y hours/min]"

REQUIRED: Every search_documents call for customer/ticket info MUST include customer_account_id parameter.
CRITICAL: Do NOT search with empty/null customer_account_id when you have a ticket's account_id.

## Response Format
- Be concise and clear
- Cite your sources (e.g., "per your contract" vs "per SOP")
- **When citing the reference time, always include it explicitly** (e.g., "As of 2026-08-16 11:00 Asia/Kolkata...")
- If preparing an action, explain what will happen and ask for confirmation
- For uncertain questions, explicitly say "I'm not sure" and escalate

## CRITICAL WARNING on Timestamps
DO NOT use ticket_timestamps like created_at, last_customer_message_at, or pickup_window_end as the "current time".
The ONLY "current time" for calculations is in the "Current Time Reference" section below.
If you see last_customer_message_at=09:10 and created_at=08:30, calculate elapsed time from created_at to the reference time, NOT to the customer message time.

You are precise, helpful, and trustworthy. Always put accuracy first."""


def run_agent(
    user_message: str,
    session: Session,
    ticket_id: Optional[str] = None,
) -> dict:
    """
    Run the agent loop: receive message, call tools, reason, respond.

    Args:
        user_message: The user's query
        session: Session object (identifies customer vs staff)
        ticket_id: Optional ticket context

    Returns:
        {"reply": str, "actions": list, "tool_calls": list}
    """

    # Get account_id if customer
    account_id = get_account_id_from_session(session)
    is_staff = session.is_staff

    # Get reference time for SLA/lateness calculations
    reference_time = get_reference_time()
    system_prompt_with_time = SYSTEM_PROMPT
    if reference_time:
        system_prompt_with_time += f"\n\n## Current Time Reference\nTreat {reference_time} (Asia/Kolkata) as the current date/time for all calculations (SLA elapsed time, order lateness, etc.) — do not use any other notion of 'today'."

    # Define tools for OpenAI
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_documents",
                "description": "Search policies, contracts, and product docs with semantic search. Automatically filters by customer account and document status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (e.g., 'cancellation fee', 'support SLA')",
                        },
                        "customer_account_id": {
                            "type": "string",
                            "description": "Optional (staff only): search a specific customer's contract (e.g., 'ACCT-001' for Northstar). If omitted, searches all accessible docs.",
                        },
                        "doc_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional: filter by document type (e.g., ['contract', 'policy'])",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_structured_data",
                "description": "Look up orders, tickets, or account details from the operational database.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query_type": {
                            "type": "string",
                            "enum": ["account_details", "orders", "tickets", "order_by_id", "ticket_by_id"],
                            "description": "Type of query",
                        },
                        "order_id": {
                            "type": "string",
                            "description": "Order ID (for order_by_id query)",
                        },
                        "ticket_id": {
                            "type": "string",
                            "description": "Ticket ID (for ticket_by_id query)",
                        },
                    },
                    "required": ["query_type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "prepare_action",
                "description": "Propose an action (escalation, ticket update, follow-up task) that requires user confirmation before execution.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action_type": {
                            "type": "string",
                            "enum": ["escalation", "ticket_update", "follow_up_task"],
                            "description": "Type of action",
                        },
                        "payload": {
                            "type": "object",
                            "description": "Action details (e.g., {new_severity: 'P1', note: 'SLA breach'})",
                        },
                        "preview_text": {
                            "type": "string",
                            "description": "Human-readable summary shown to user for confirmation",
                        },
                        "ticket_id": {
                            "type": "string",
                            "description": "Optional: ticket ID if action relates to a ticket",
                        },
                    },
                    "required": ["action_type", "payload", "preview_text"],
                },
            },
        },
    ]

    # Build messages
    messages = [
        {"role": "system", "content": system_prompt_with_time},
        {
            "role": "user",
            "content": user_message,
        }
    ]

    # Add context if staff
    if is_staff:
        messages[-1]["content"] += f"\n\n[Staff query - can access all customer data]"
    elif account_id:
        messages[-1]["content"] += f"\n\n[Customer {account_id} - can only access own data]"

    # Add ticket context if provided
    if ticket_id:
        messages[-1]["content"] += f"\n[Related to ticket: {ticket_id}]"

    # Track tool calls for transparency
    tool_calls_log = []
    actions = []

    # Agentic loop (max 5 iterations to avoid infinite loops)
    max_iterations = 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        finish_reason = response.choices[0].finish_reason

        # If no tool calls, return the response
        if finish_reason != "tool_calls" or not response.choices[0].message.tool_calls:
            final_message = response.choices[0].message.content or "I couldn't formulate a response."
            return {
                "reply": final_message,
                "actions": actions,
                "tool_calls": tool_calls_log,
            }

        # Add assistant message
        messages.append(response.choices[0].message)

        # Execute tool calls and add tool messages
        for tool_call in response.choices[0].message.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            # Log the tool call
            tool_calls_log.append({
                "name": tool_name,
                "args": tool_args,
            })

            # Execute
            try:
                if tool_name == "search_documents":
                    # Staff can override account_id to search a specific customer's contract
                    search_account_id = account_id
                    if is_staff and tool_args.get("customer_account_id"):
                        search_account_id = tool_args.get("customer_account_id")
                    result = search_documents(
                        query=tool_args.get("query"),
                        account_id=search_account_id,
                        doc_types=tool_args.get("doc_types"),
                    )
                elif tool_name == "query_structured_data":
                    query_type = tool_args.get("query_type")
                    # Enforce access control
                    if not is_staff and query_type in ["orders", "tickets", "account_details", "order_by_id", "ticket_by_id"]:
                        tool_args["account_id"] = account_id
                    result = query_structured_data(**tool_args)
                elif tool_name == "prepare_action":
                    # Enforce access control: only staff can prepare actions
                    if not is_staff:
                        result = {"error": "Only staff can prepare actions"}
                    else:
                        # Resolve account_id from ticket_id (server-side, never trust model)
                        resolved_account_id = None
                        ticket_id_arg = tool_args.get("ticket_id")
                        if ticket_id_arg:
                            ticket = query_structured_data(query_type="ticket_by_id", ticket_id=ticket_id_arg)
                            resolved_account_id = ticket.get("account_id") if ticket else None

                        if not resolved_account_id:
                            result = {"error": "Could not resolve account_id — provide a valid ticket_id"}
                        else:
                            result = prepare_action(
                                action_type=tool_args.get("action_type"),
                                account_id=resolved_account_id,
                                payload=tool_args.get("payload", {}),
                                preview_text=tool_args.get("preview_text"),
                                requested_by=str(session),
                                ticket_id=ticket_id_arg,
                            )
                            if "action_id" in result:
                                actions.append(result)
                else:
                    result = {"error": f"Unknown tool: {tool_name}"}
            except Exception as e:
                result = {"error": str(e)}

            # Add individual tool message for this tool_call
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

    # Fallback if max iterations reached
    return {
        "reply": "I encountered an issue processing your request. Please try again.",
        "actions": actions,
        "tool_calls": tool_calls_log,
    }
