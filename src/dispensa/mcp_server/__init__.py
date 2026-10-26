from dispensa.mcp_server import server
from dispensa.mcp_server.runtime import mcp

# Importing the tool modules registers their tools on `mcp`.
__all__ = ["mcp", "server"]
