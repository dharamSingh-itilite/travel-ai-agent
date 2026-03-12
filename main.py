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


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Process a user message through the AI agent."""
    agent_message = build_agent_message(request)
    print(f"[INFO] Received: {request.message[:100]}")
    print(f"[INFO] Agent message: {agent_message[:200]}")
    result = await run_agent(agent_message, request.thread_id)
    print(f"[INFO] Response: {result[:100]}")
    return ChatResponse(
        trip_id=request.trip_id,
        session_id=request.thread_id,
        message=result,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
