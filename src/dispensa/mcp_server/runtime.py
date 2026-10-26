import logging
from functools import cache
from typing import TYPE_CHECKING

from mcp.server import MCPServer
from openai import OpenAI

from dispensa.deps import build_deps
from dispensa.settings import Settings

if TYPE_CHECKING:
    from dispensa.deps import Deps

logger = logging.getLogger(__name__)

# FastMCP was renamed MCPServer in the 2.0 SDK; the instance is still the object
# tools hang off and that `mcp.run(...)` starts.
mcp = MCPServer("dispensa")


@cache
def get_deps() -> Deps:
    """Wire the repositories once per process, lazily on the first tool call."""
    logger.info("Wiring repositories on first use")
    return build_deps(Settings().database_url)


@cache
def get_openai_client() -> OpenAI:
    """Create one OpenAI client per process for query embeddings."""
    return OpenAI(api_key=Settings().require_openai_api_key())
