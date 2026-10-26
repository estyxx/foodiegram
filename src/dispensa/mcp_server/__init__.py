from dispensa.mcp_server import server, write_tools
from dispensa.mcp_server.runtime import mcp

# Importing the tool modules registers their tools on `mcp`.
__all__ = ["mcp", "server", "write_tools"]
