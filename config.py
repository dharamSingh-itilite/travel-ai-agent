"""Application configuration loaded from environment and config files."""

import json
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

CONFIG_DIR = Path(__file__).parent
MCP_SERVERS_FILE = CONFIG_DIR / "mcp_servers.json"


class McpServerConfig(BaseModel):
    name: str
    transport: str = "stdio"  # "stdio" or "sse"
    # Stdio fields
    command: str | None = None
    args: list[str] = []
    env: dict[str, str] = {}
    # SSE fields
    url: str | None = None


def load_mcp_servers() -> list[McpServerConfig]:
    """Load MCP server configurations from mcp_servers.json."""
    if not MCP_SERVERS_FILE.exists():
        print(f"[WARN] MCP servers config not found at {MCP_SERVERS_FILE}")
        return []

    raw = json.loads(MCP_SERVERS_FILE.read_text())
    servers = [McpServerConfig(**s) for s in raw["servers"]]
    print(f"[INFO] Loaded {len(servers)} MCP server(s): {[s.name for s in servers]}")
    return servers
