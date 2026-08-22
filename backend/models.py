from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# ---------------------------------------------------------------------------
# Structured data models (from database)
# ---------------------------------------------------------------------------

class Account(BaseModel):
    account_id: str
    account_name: str
    plan: str
    status: str
    csm: Optional[str]
    contract_file: Optional[str]
    premium_support: bool

    class Config:
        from_attributes = True

class Order(BaseModel):
    order_id: str
    account_id: str
    carrier: str
    status: str
    booked_at: datetime
    pickup_window_start: datetime
    pickup_window_end: datetime
    pickup_actual_at: Optional[datetime]
    shipment_fee_inr: float
    carrier_fault: bool
    customer_fault: bool
    cancellation_requested_at: Optional[datetime]
    notes: Optional[str]

    class Config:
        from_attributes = True

class Ticket(BaseModel):
    ticket_id: str
    account_id: str
    created_at: datetime
    status: str
    subject: str
    description: str
    channel: Optional[str]
    assigned_to: Optional[str]
    last_customer_message_at: Optional[datetime]
    historical_resolution: Optional[str]

    class Config:
        from_attributes = True

class DocChunk(BaseModel):
    id: UUID
    source_file: str
    doc_type: str
    status: str
    customer_account_id: Optional[str]
    effective_date: Optional[str]
    section_number: str
    section_title: str
    content: str

    class Config:
        from_attributes = True

class AgentAction(BaseModel):
    action_id: UUID
    action_type: str
    account_id: str
    ticket_id: Optional[str]
    requested_by: str
    payload: dict
    preview_text: str
    status: str
    created_at: datetime
    executed_at: Optional[datetime]

    class Config:
        from_attributes = True
