"""Tests for the /chat and /health API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.fixture
def mock_agent():
    """Mock agent initialization and run so tests don't need MCP servers or API keys."""
    with (
        patch("main.initialize_agent", new_callable=AsyncMock) as mock_init,
        patch("main.shutdown_agent", new_callable=AsyncMock) as mock_shutdown,
        patch("main.run_agent", new_callable=AsyncMock) as mock_run,
    ):
        yield mock_init, mock_shutdown, mock_run


@pytest_asyncio.fixture
async def client(mock_agent):
    """Async HTTP client for testing FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac, mock_agent


@pytest.mark.asyncio
async def test_health(client):
    ac, _ = client
    response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_chat_success(client):
    ac, (_, _, mock_run) = client
    mock_run.return_value = "Hello! How can I help you?"

    response = await ac.post("/chat", json={"message": "Hi there", "thread_id": "t1"})

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Hello! How can I help you?"
    assert data["session_status"] == "OPEN"
    mock_run.assert_called_once_with("Hi there", "t1")


@pytest.mark.asyncio
async def test_chat_approved_closes_session(client):
    ac, (_, _, mock_run) = client
    mock_run.return_value = "Status: APPROVED\nMessage: Trip approved for $500."

    response = await ac.post("/chat", json={"message": "approve", "thread_id": "t1"})

    assert response.status_code == 200
    data = response.json()
    assert data["session_status"] == "CLOSED"
    assert data["message"] == "Trip approved for $500."


@pytest.mark.asyncio
async def test_chat_rejected_closes_session(client):
    ac, (_, _, mock_run) = client
    mock_run.return_value = "Status: REJECTED\nMessage: Trip rejected per user request."

    response = await ac.post("/chat", json={"message": "reject", "thread_id": "t1"})

    assert response.status_code == 200
    data = response.json()
    assert data["session_status"] == "CLOSED"
    assert data["message"] == "Trip rejected per user request."


@pytest.mark.asyncio
async def test_chat_empty_message(client):
    ac, (_, _, mock_run) = client
    mock_run.return_value = "I received an empty message."

    response = await ac.post("/chat", json={"message": "", "thread_id": "t2"})

    assert response.status_code == 200
    assert "message" in response.json()


@pytest.mark.asyncio
async def test_chat_missing_message_field(client):
    ac, _ = client
    response = await ac.post("/chat", json={"text": "wrong field", "thread_id": "t0"})

    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_chat_no_body(client):
    ac, _ = client
    response = await ac.post("/chat")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_long_message(client):
    ac, (_, _, mock_run) = client
    long_message = "Tell me a story " * 100
    mock_run.return_value = "Once upon a time..."

    response = await ac.post("/chat", json={"message": long_message, "thread_id": "t3"})

    assert response.status_code == 200
    assert response.json()["message"] == "Once upon a time..."
