import logging
import os

import anyio
import httpx
import mcp.types as types
from aci.meta_functions import ACIExecuteFunction, ACISearchFunctions
from aci.types.enums import FunctionDefinitionFormat
from mcp.server.lowlevel import Server

from .common import runners

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

VIBEOPS_BASE_URL = os.getenv("VIBEOPS_BASE_URL", "https://vibeops.aci.dev")

server = Server("aci-mcp-vibeops")


aci_search_functions = ACISearchFunctions.to_json_schema(FunctionDefinitionFormat.ANTHROPIC)
aci_execute_function = ACIExecuteFunction.to_json_schema(FunctionDefinitionFormat.ANTHROPIC)

# TODO: Cursor's auto mode doesn't work well with MCP. (generating wrong type of parameters and
# the type validation logic is not working correctly). So temporarily we're removing the limit and
# offset parameters from the search function.
aci_search_functions["input_schema"]["properties"].pop("limit", None)
aci_search_functions["input_schema"]["properties"].pop("offset", None)


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools.
    """
    return [
        types.Tool(
            name=aci_search_functions["name"],
            description=aci_search_functions["description"],
            inputSchema=aci_search_functions["input_schema"],
        ),
        types.Tool(
            name=aci_execute_function["name"],
            description=aci_execute_function["description"],
            inputSchema=aci_execute_function["input_schema"],
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests.
    """
    if not arguments:
        arguments = {}

    try:
        if name == aci_search_functions["name"]:
            response = httpx.get(
                f"{VIBEOPS_BASE_URL}/api/v1/functions/search",
                headers={"Authorization": f"Bearer {os.getenv('VIBEOPS_API_KEY')}"},
                params={"intent": arguments["intent"]},
            )
            return [types.TextContent(type="text", text=response.text)]
        elif name == aci_execute_function["name"]:
            response = httpx.post(
                f"{VIBEOPS_BASE_URL}/api/v1/functions/{arguments['function_name']}/execute",
                headers={"Authorization": f"Bearer {os.getenv('VIBEOPS_API_KEY')}"},
                json={
                    "function_input": arguments["function_arguments"],
                },
            )
            return [types.TextContent(type="text", text=response.text)]
        else:
            return [types.TextContent(type="text", text="Not implemented")]

    except Exception as e:
        return [
            types.TextContent(
                type="text",
                text=f"Failed to execute tool, error: {e}",
            )
        ]


def start(transport: str, port: int) -> None:
    logger.info("Starting MCP server...")

    if transport == "sse":
        anyio.run(runners.run_sse_async, server, "0.0.0.0", port)
    else:
        anyio.run(runners.run_stdio_async, server)
