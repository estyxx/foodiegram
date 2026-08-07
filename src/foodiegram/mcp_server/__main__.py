import logging
import sys

from foodiegram.mcp_server.server import mcp

# stdio is the protocol channel, so every log line goes to stderr; configuring
# it here (not in the library modules) is the one place we own the entrypoint.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logging.getLogger(__name__).info("Starting dispensa MCP server over stdio")

mcp.run(transport="stdio")
