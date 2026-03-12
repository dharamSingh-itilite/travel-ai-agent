"""LangGraph agent that uses MCP tools to accomplish tasks."""

import os

from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from config import load_mcp_servers
from mcp_client import McpClient

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

mcp_client = McpClient()
memory = MemorySaver()
_agent = None


async def initialize_agent():
    """Connect to MCP servers and build the agent once."""
    global _agent
    servers = load_mcp_servers()
    await mcp_client.connect(servers)
    _agent = build_agent()
    print(f"[INFO] Agent initialized with {len(mcp_client.tools)} tool(s)")


async def shutdown_agent():
    """Cleanup MCP connections."""
    await mcp_client.cleanup()


def build_agent():
    """Build and return a LangGraph ReAct agent with MCP tools."""
    llm = ChatAnthropic(model=MODEL, temperature=0)

    system_prompt = (
        "You are a helpful AI assistant. Use the available tools to accomplish "
        "the user's request. Be concise and action-oriented. If no tool is "
        "needed, respond directly."
    )

    agent = create_react_agent(
        model=llm,
        tools=mcp_client.tools,
        prompt=system_prompt,
        checkpointer=memory,
    )
    return agent


async def run_agent(user_message: str, thread_id: str) -> str:
    """Run the agent with a user message and return the final response."""
    inputs = {"messages": [("user", user_message)]}
    config = {"configurable": {"thread_id": thread_id}}
    response = await _agent.ainvoke(inputs, config=config)

    # Extract the last AI message
    ai_messages = [m for m in response["messages"] if m.type == "ai" and m.content]
    if ai_messages:
        return ai_messages[-1].content

    return "I couldn't generate a response. Please try again."
