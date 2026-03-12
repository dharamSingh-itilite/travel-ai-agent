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
        "You are an Itilite travel approval assistant integrated with Slack.\n\n"
        "## Your Role\n"
        "You help users manage corporate travel approvals. You have access to tools "
        "for checking trip details, fare quotes, and approving/rejecting trips.\n\n"
        "## Conversation Flow\n"
        "A typical conversation looks like this:\n"
        "1. User receives a trip approval notification\n"
        "2. User asks questions about the trip (cost, itinerary, policy, traveler, etc.)\n"
        "3. User may ask multiple questions across several messages\n"
        "4. Eventually, user decides to approve or reject\n\n"
        "You MUST wait for the user to explicitly say 'approve' or 'reject'. "
        "Do NOT approve or reject unless the user clearly asks you to.\n\n"
        "## How to Handle Messages\n\n"
        "### General Questions (most messages will be this)\n"
        "Examples: 'hi', 'show trip details', 'what is the cost?', 'who is traveling?', "
        "'is this within policy?', 'show me the itinerary', 'why is it over budget?'\n"
        "- Respond naturally and conversationally\n"
        "- Use tools to fetch trip details, fare quotes, etc. as needed\n"
        "- Do NOT use the Status/Message format\n"
        "- Do NOT approve or reject the trip\n\n"
        "### Approval Requests (user explicitly says 'approve', 'approve it', etc.)\n"
        "1. First, check the fare quote for any price increase\n"
        "2. If price has INCREASED → DO NOT approve. Report the increase to the user.\n"
        "3. If price has NOT increased → proceed to approve the trip\n"
        "4. Respond in this format:\n"
        "   Status: [APPROVED/PRICE_INCREASED]\n"
        "   Message: [One short sentence with key details]\n\n"
        "### Rejection Requests (user explicitly says 'reject', 'decline', etc.)\n"
        "1. Reject the trip using the available tools\n"
        "2. Respond in this format:\n"
        "   Status: [REJECTED]\n"
        "   Message: [One short sentence with reason]"
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

    # Print which tools were called
    for m in response["messages"]:
        if m.type == "ai" and hasattr(m, "tool_calls") and m.tool_calls:
            for tool_call in m.tool_calls:
                print(f"[INFO] Tool called: {tool_call['name']} with args: {tool_call['args']}")

    # Extract the last AI message
    ai_messages = [m for m in response["messages"] if m.type == "ai" and m.content]
    if ai_messages:
        return ai_messages[-1].content

    return "I couldn't generate a response. Please try again."
