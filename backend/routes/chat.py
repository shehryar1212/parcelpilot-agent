from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from auth import Session, get_session
from agent import run_agent

router = APIRouter()

class MessageRequest(BaseModel):
    message: str
    ticket_id: Optional[str] = None  # context for support tickets

class MessageResponse(BaseModel):
    reply: str
    actions: list = []
    tool_calls: list = []  # for transparency in frontend

@router.post("/chat/message")
async def chat_message(
    req: MessageRequest,
    session: Session = Depends(get_session),
):
    """Chat endpoint. Routes to agent loop."""
    print(f"\n{'='*60}")
    print(f"Chat message from {session}")
    print(f"Message: {req.message}")
    print(f"{'='*60}\n")

    result = run_agent(
        user_message=req.message,
        session=session,
        ticket_id=req.ticket_id,
    )

    return MessageResponse(
        reply=result["reply"],
        actions=result["actions"],
        tool_calls=result["tool_calls"],
    )

@router.get("/chat/history")
async def chat_history(
    session: Session = Depends(get_session),
    ticket_id: Optional[str] = None,
):
    """Get conversation history for a ticket or general chat."""
    # TODO: Implement if needed
    return {"messages": []}
