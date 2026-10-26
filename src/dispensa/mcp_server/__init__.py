from dispensa.mcp_server import pantry_tools, server, write_tools
from dispensa.mcp_server.runtime import mcp

# Importing the tool modules registers their tools on `mcp`.
__all__ = ["mcp", "pantry_tools", "server", "write_tools"]
