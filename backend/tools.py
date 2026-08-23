"""
ParcelPilot Agent Tools

Three core tools:
1. search_documents - retrieval with metadata filtering for source precedence
2. query_structured_data - lookup orders/tickets/accounts
3. prepare_action/execute_action - two-phase action confirmation
"""

from sqlalchemy import text
from db.config import get_connection
from models import DocChunk, Order, Ticket, Account, AgentAction
from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime
import json

# ---------------------------------------------------------------------------
# Helper: Resolve account ID from name or ID
# ---------------------------------------------------------------------------

def resolve_account_id(identifier: str) -> Optional[str]:
    """Accept either an account_id or a customer name; resolve to account_id."""
    if not identifier:
        return None
    conn = get_connection()
    # First try exact account_id match
    row = conn.execute(
        text("SELECT account_id FROM accounts WHERE account_id = :id"),
        {"id": identifier}
    ).fetchone()
    if row:
        return row[0]
    # Fall back to name lookup
    row = conn.execute(
        text("SELECT account_id FROM accounts WHERE account_name ILIKE :name"),
        {"name": f"%{identifier}%"}
    ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Tool 1: search_documents
# ---------------------------------------------------------------------------

def search_documents(
    query: str,
    account_id: Optional[str] = None,
    doc_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Search documents with metadata filtering for source precedence.

    Precedence: contract > current policy > product doc > deprecated

    Args:
        query: Search query (will be embedded and searched)
        account_id: Customer account ID (filters to customer contracts + general docs)
        doc_types: Specific doc types to include (e.g., ['contract', 'policy'])

    Returns:
        List of doc chunks, ordered by relevance
    """
    from openai import OpenAI
    import os

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Embed the query
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query,
    )
    query_embedding = response.data[0].embedding

    conn = get_connection()

    # Build filter conditions with parameterized queries
    filters = ["status != 'deprecated'"]
    params = {}

    # If account_id provided, include their contract + general docs
    if account_id:
        filters.append("(customer_account_id = :account_id OR customer_account_id IS NULL)")
        params["account_id"] = account_id
    else:
        # Staff searching without specific account: only return general docs, not other customers' contracts
        filters.append("customer_account_id IS NULL")

    # If doc_types specified, filter by those
    if doc_types:
        filters.append("doc_type = ANY(:doc_types)")
        params["doc_types"] = doc_types

    where_clause = " AND ".join(filters)

    # Format embedding as PostgreSQL vector literal (not a parameter)
    # Parameters + ::vector cast don't work together in SQLAlchemy; use string interpolation instead
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    # When account_id is scoped, return full set (20); else 10 for staff unscoped searches
    # Small corpus (~17 chunks) means tight LIMIT risks dropping the relevant contract
    limit = 20 if account_id else 10

    # Search by embedding similarity
    sql = f"""
    SELECT
        id, source_file, doc_type, status, customer_account_id,
        section_number, section_title, content,
        1 - (embedding <=> '{embedding_str}'::vector) as similarity
    FROM doc_chunks
    WHERE {where_clause}
    ORDER BY similarity DESC
    LIMIT {limit}
    """

    try:
        result = conn.execute(text(sql), params)
        rows = result.fetchall()
        chunks = [
            {
                "id": str(row[0]),
                "source_file": row[1],
                "doc_type": row[2],
                "status": row[3],
                "customer_account_id": row[4],
                "section_number": row[5],
                "section_title": row[6],
                "content": row[7],
                "similarity": float(row[8]),
            }
            for row in rows
        ]
        return chunks
    except Exception as e:
        print(f"Search error: {e}")
        return []


# ---------------------------------------------------------------------------
# Tool 2: query_structured_data
# ---------------------------------------------------------------------------

def query_structured_data(
    query_type: str,
    account_id: Optional[str] = None,
    order_id: Optional[str] = None,
    ticket_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query structured operational data.

    Args:
        query_type: 'account_details', 'orders', 'tickets', 'order_by_id', 'ticket_by_id'
        account_id: Filter to specific account
        order_id: Get specific order
        ticket_id: Get specific ticket

    Returns:
        Query results
    """
    conn = get_connection()

    if query_type == "account_details" and account_id:
        result = conn.execute(
            text("SELECT * FROM accounts WHERE account_id = :id"),
            {"id": account_id}
        )
        row = result.fetchone()
        if row:
            return {
                "account_id": row[0],
                "account_name": row[1],
                "plan": row[2],
                "status": row[3],
                "csm": row[4],
                "contract_file": row[5],
                "premium_support": row[6],
            }
        return None

    elif query_type == "orders" and account_id:
        result = conn.execute(
            text("SELECT * FROM orders WHERE account_id = :id ORDER BY booked_at DESC"),
            {"id": account_id}
        )
        rows = result.fetchall()
        return [
            {
                "order_id": row[0],
                "account_id": row[1],
                "carrier": row[2],
                "status": row[3],
                "booked_at": row[4].isoformat() if row[4] else None,
                "pickup_window_start": row[5].isoformat() if row[5] else None,
                "pickup_window_end": row[6].isoformat() if row[6] else None,
                "pickup_actual_at": row[7].isoformat() if row[7] else None,
                "shipment_fee_inr": float(row[8]),
                "carrier_fault": row[9],
                "customer_fault": row[10],
                "cancellation_requested_at": row[11].isoformat() if row[11] else None,
                "notes": row[12],
            }
            for row in rows
        ]

    elif query_type == "tickets" and account_id:
        result = conn.execute(
            text("SELECT * FROM tickets WHERE account_id = :id ORDER BY created_at DESC"),
            {"id": account_id}
        )
        rows = result.fetchall()
        return [
            {
                "ticket_id": row[0],
                "account_id": row[1],
                "created_at": row[2].isoformat() if row[2] else None,
                "status": row[3],
                "subject": row[4],
                "description": row[5],
                "channel": row[6],
                "assigned_to": row[7],
                "last_customer_message_at": row[8].isoformat() if row[8] else None,
                "historical_resolution": row[9],
            }
            for row in rows
        ]

    elif query_type == "order_by_id" and order_id:
        sql = "SELECT * FROM orders WHERE order_id = :id"
        params = {"id": order_id}
        if account_id:
            sql += " AND account_id = :account_id"
            params["account_id"] = account_id
        result = conn.execute(text(sql), params)
        row = result.fetchone()
        if row:
            return {
                "order_id": row[0],
                "account_id": row[1],
                "carrier": row[2],
                "status": row[3],
                "booked_at": row[4].isoformat() if row[4] else None,
                "pickup_window_start": row[5].isoformat() if row[5] else None,
                "pickup_window_end": row[6].isoformat() if row[6] else None,
                "pickup_actual_at": row[7].isoformat() if row[7] else None,
                "shipment_fee_inr": float(row[8]),
                "carrier_fault": row[9],
                "customer_fault": row[10],
                "cancellation_requested_at": row[11].isoformat() if row[11] else None,
                "notes": row[12],
            }
        return None

    elif query_type == "ticket_by_id" and ticket_id:
        sql = "SELECT * FROM tickets WHERE ticket_id = :id"
        params = {"id": ticket_id}
        if account_id:
            sql += " AND account_id = :account_id"
            params["account_id"] = account_id
        result = conn.execute(text(sql), params)
        row = result.fetchone()
        if row:
            return {
                "ticket_id": row[0],
                "account_id": row[1],
                "created_at": row[2].isoformat() if row[2] else None,
                "status": row[3],
                "subject": row[4],
                "description": row[5],
                "channel": row[6],
                "assigned_to": row[7],
                "last_customer_message_at": row[8].isoformat() if row[8] else None,
                "historical_resolution": row[9],
            }
        return None

    return None


# ---------------------------------------------------------------------------
# Tool 3: prepare_action / execute_action
# ---------------------------------------------------------------------------

def prepare_action(
    action_type: str,
    account_id: str,
    payload: Dict[str, Any],
    preview_text: str,
    requested_by: str,
    ticket_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Prepare an action for confirmation (escalation, ticket update, follow-up task).
    Inserts as pending_confirmation. User must confirm via execute_action.

    Args:
        action_type: 'escalation', 'ticket_update', 'follow_up_task'
        account_id: Customer account ID
        payload: Action details (JSON)
        preview_text: Human-readable summary shown for confirmation
        requested_by: Session identity (e.g., 'customer:ACCT-001' or 'staff:support')
        ticket_id: Optional ticket ID if related to a ticket

    Returns:
        Action details with action_id for confirmation
    """
    conn = get_connection()
    action_id = str(uuid4())

    sql = """
    INSERT INTO agent_actions (
        action_id, action_type, account_id, ticket_id, requested_by, payload, preview_text, status, created_at
    ) VALUES (
        :action_id, :action_type, :account_id, :ticket_id, :requested_by, :payload, :preview_text, 'pending_confirmation', NOW()
    )
    """

    conn.execute(
        text(sql),
        {
            "action_id": action_id,
            "action_type": action_type,
            "account_id": account_id,
            "ticket_id": ticket_id,
            "requested_by": requested_by,
            "payload": json.dumps(payload),
            "preview_text": preview_text,
        }
    )
    conn.commit()

    return {
        "action_id": action_id,
        "status": "pending_confirmation",
        "preview_text": preview_text,
    }


def execute_action(action_id: str) -> Dict[str, Any]:
    """
    Execute a pending action (flip from pending_confirmation to executed).

    Args:
        action_id: UUID of the action to execute

    Returns:
        Updated action details
    """
    conn = get_connection()

    # Verify action exists and is pending
    result = conn.execute(
        text("SELECT * FROM agent_actions WHERE action_id = :id AND status = 'pending_confirmation'"),
        {"id": action_id}
    )
    row = result.fetchone()
    if not row:
        return {"error": "Action not found or already executed"}

    # Execute it
    conn.execute(
        text("UPDATE agent_actions SET status = 'executed', executed_at = NOW() WHERE action_id = :id"),
        {"id": action_id}
    )
    conn.commit()

    return {
        "action_id": action_id,
        "status": "executed",
        "executed_at": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Helper: Get account ID from session
# ---------------------------------------------------------------------------

def get_account_id_from_session(session) -> Optional[str]:
    """Extract account_id if session is a customer."""
    if session.is_customer:
        return session.account_id
    return None
