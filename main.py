"""FastAPI application with /chat endpoint for the AI agent."""

from contextlib import asynccontextmanager

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
    message: str
    thread_id: str
    trip_id: str | None = None
    token_id: str | None = None
    selection_id: str | None = None


class ChatResponse(BaseModel):
    trip_id: str | None = None
    session_id: str | None = None
    message: str
    session_status: str = "OPEN"  # "OPEN" or "CLOSED"


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


def detect_session_status(response: str) -> str:
    """Return CLOSED if the agent approved/rejected the trip, else OPEN."""
    for line in response.split("\n"):
        stripped = line.strip().lower()
        if stripped.startswith("status:"):
            status_value = stripped.split(":", 1)[1].strip()
            if "approved" in status_value or "rejected" in status_value:
                return "CLOSED"
    return "OPEN"


def extract_short_message(response: str) -> str:
    """Extract the Message: line if present, otherwise return full response."""
    for line in response.split("\n"):
        if line.strip().lower().startswith("message:"):
            return line.split(":", 1)[1].strip()
    return response


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Process a user message through the AI agent."""
    agent_message = build_agent_message(request)
    print(f"[INFO] Received: {request.message[:100]}")
    print(f"[INFO] Agent message: {agent_message[:200]}")
    result = await run_agent(agent_message, request.thread_id)
    print(f"[INFO] Response: {result[:100]}")
    session_status = detect_session_status(result)
    return ChatResponse(
        trip_id=request.trip_id,
        session_id=request.thread_id,
        message=extract_short_message(result),
        session_status=session_status,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
