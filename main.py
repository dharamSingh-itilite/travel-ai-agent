"""FastAPI application with /chat endpoint for the AI agent."""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from agent import initialize_agent, run_agent, shutdown_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: connect MCP servers. Shutdown: cleanup."""
    await initialize_agent()
    yield
    await shutdown_agent()


app = FastAPI(title="Slack Itilite Agent", lifespan=lifespan)


class ChatRequest(BaseModel):
    """Request model for structured tool calls."""
    session_id: str
    trip_id: Optional[str] = None
    token_id: Optional[str] = None
    message: Optional[str] = None
    selection_id: Optional[str] = None


class ChatResponse(BaseModel):
    trip_id: Optional[str] = None
    session_id: Optional[str] = None
    message: Optional[str] = None  # "APPROVED: details" or "REJECTED: reason" or "PRICE_INCREASED: details"


def build_agent_message(request: ChatRequest) -> str:
    """Build message for the agent with user message and trip context."""
    parts = [request.message]

    if request.trip_id:
        parts.append(f"Trip ID: {request.trip_id}")
    if request.token_id:
        parts.append(f"Token ID: {request.token_id}")
    if request.selection_id:
        parts.append(f"Selection ID: {request.selection_id}")

    return "\n".join(parts)


def extract_status(response: str) -> str:
    """Extract status from agent response."""
    response_lower = response.lower()
    if "price_increased" in response_lower or "price increase" in response_lower or "price has increased" in response_lower:
        return "price_increased"
    elif "approved" in response_lower:
        return "approved"
    elif "rejected" in response_lower:
        return "rejected"
    return response_lower


def extract_message(response: str) -> str:
    """Extract short message from agent response."""
    # Try to find Message: line
    lines = response.split("\n")
    for line in lines:
        if line.lower().startswith("message:"):
            return line.split(":", 1)[1].strip()
    # If no Message: line, return first 100 chars
    return response[:100] if len(response) > 100 else response


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Process a user message through the AI agent and return structured response."""
    print(f"[INFO] Received request for agent: {request}")
    agent_message = build_agent_message(request)
    print(f"[INFO] Received request - Message: {request.message}, Trip ID: {request.trip_id}")
    print(f"[INFO] Built message to agent: {agent_message}")

    result = await run_agent(agent_message, request.session_id)
    print(f"[INFO] Raw response: {result[:200]}...")

    status = extract_status(result)
    short_message = extract_message(result)

    return ChatResponse(
        trip_id=request.trip_id,
        session_id=request.session_id,
        message=f"{status.upper()}: {short_message}"
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
