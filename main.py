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


class ChatResponse(BaseModel):
    response: str


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Process a user message through the AI agent."""
    print(f"[INFO] Received: {request.message[:100]}")
    result = await run_agent(request.message, request.thread_id)
    print(f"[INFO] Response: {result[:100]}")
    return ChatResponse(response=result)


@app.get("/health")
async def health():
    return {"status": "ok"}
