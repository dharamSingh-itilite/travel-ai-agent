"""LangGraph agent that uses MCP tools to accomplish tasks."""

import os
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from config import load_mcp_servers
from mcp_client import McpClient

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
MAX_TOKENS = 1024
MAX_MESSAGES = 20
SYSTEM_PROMPT_FILE = Path(__file__).parent / "system_prompt.md"

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


def trim_to_recent(state: dict) -> dict:
    """Keep only the last MAX_MESSAGES to avoid context overflow."""
    messages = state.get("messages", [])
    if len(messages) <= MAX_MESSAGES:
        return {"llm_input_messages": messages}
    print(f"[INFO] Trimming conversation from {len(messages)} to {MAX_MESSAGES} messages")
    return {"llm_input_messages": messages[-MAX_MESSAGES:]}


def build_agent():
    """Build and return a LangGraph ReAct agent with MCP tools."""
    llm = ChatAnthropic(model=MODEL, temperature=0, max_tokens=MAX_TOKENS)
    system_prompt = SYSTEM_PROMPT_FILE.read_text()

    agent = create_react_agent(
        model=llm,
        tools=mcp_client.tools,
        prompt=system_prompt,
        checkpointer=memory,
        pre_model_hook=trim_to_recent,
    )
    return agent


async def run_agent(user_message: str, thread_id: str) -> str:
    """Run the agent with a user message and return the final response."""
    if _agent is None:
        print("[ERROR] Agent not initialized")
        return "Agent is not ready. Please try again later."

    inputs = {"messages": [("user", user_message)]}
    config = {"configurable": {"thread_id": thread_id}}
    response = await _agent.ainvoke(inputs, config=config)

    # Print which tools were called
    for m in response["messages"]:
        if m.type == "ai" and hasattr(m, "tool_calls") and m.tool_calls:
            for tool_call in m.tool_calls:
                print(f"[INFO] Tool called: {tool_call['name']} with args: {tool_call['args']}")

    # Prefer final AI message without tool calls; fall back to last AI message with content
    all_ai = [m for m in response["messages"] if m.type == "ai" and m.content]
    final_only = [m for m in all_ai if not getattr(m, "tool_calls", None)]
    ai_message = (final_only or all_ai)[-1] if (final_only or all_ai) else None
    if ai_message:
        return ai_message.content

    return "I couldn't generate a response. Please try again."
