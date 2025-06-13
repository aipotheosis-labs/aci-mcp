import json
import logging

import anyio
import mcp.types as types
from aci import ACI
from aci.meta_functions import ACIExecuteFunction, ACISearchFunctions
from aci.types.enums import FunctionDefinitionFormat
from mcp.server.lowlevel import Server

from .common import runners

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

aci = ACI()
server: Server = Server("aci-mcp-unified")

ALLOWED_APPS_ONLY = False
LINKED_ACCOUNT_OWNER_ID = ""

aci_search_functions = ACISearchFunctions.to_json_schema(FunctionDefinitionFormat.ANTHROPIC)
aci_execute_function = ACIExecuteFunction.to_json_schema(FunctionDefinitionFormat.ANTHROPIC)

# TODO: Cursor's auto mode doesn't work well with MCP. (generating wrong type of parameters and
# the type validation logic is not working correctly). So temporarily we're removing the limit and
# offset parameters from the search function.
aci_search_functions["input_schema"]["properties"].pop("limit", None)
aci_search_functions["input_schema"]["properties"].pop("offset", None)


def _set_up(allowed_apps_only: bool, linked_account_owner_id: str):
    """
    Set up global variables
    """
    global ALLOWED_APPS_ONLY, LINKED_ACCOUNT_OWNER_ID

    ALLOWED_APPS_ONLY = allowed_apps_only
    LINKED_ACCOUNT_OWNER_ID = linked_account_owner_id


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

    # TODO: if it's ACI_SEARCH_FUNCTIONS, populate default values for limit and offset because we
    # removed them from the input schema at the top of this file.
    if name == aci_search_functions["name"]:
        arguments["limit"] = 15
        arguments["offset"] = 0

    # TODO: temporary solution to support multi-user usecases due to the limitation of MCP protocol.
    # What happens here is that we allow user (MCP clients) to pass in the
    # "aci_override_linked_account_owner_id" parameter for the ACI_EXECUTE_FUNCTION tool call
    # (apart from the "function_name" and "function_arguments" parameters), to override the
    # default value of the "linked_account_owner_id".
    # The --linked-account-owner-id flag that we use to start the MCP server will be used as the
    # default value of the "linked_account_owner_id".
    linked_account_owner_id = LINKED_ACCOUNT_OWNER_ID
    if name == aci_execute_function["name"] and "aci_override_linked_account_owner_id" in arguments:
        linked_account_owner_id = str(arguments["aci_override_linked_account_owner_id"])
        del arguments["aci_override_linked_account_owner_id"]

    try:
        result = aci.handle_function_call(
            name,
            arguments,
            linked_account_owner_id=linked_account_owner_id,
            allowed_apps_only=ALLOWED_APPS_ONLY,
            format=FunctionDefinitionFormat.ANTHROPIC,
        )
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result),
            )
        ]
    except Exception as e:
        return [
            types.TextContent(
                type="text",
                text=f"Failed to execute tool, error: {e}",
            )
        ]


def start(allowed_apps_only: bool, linked_account_owner_id: str, transport: str, port: int) -> None:
    logger.info("Starting MCP server...")

    _set_up(allowed_apps_only=allowed_apps_only, linked_account_owner_id=linked_account_owner_id)

    if transport == "sse":
        anyio.run(runners.run_sse_async, server, "0.0.0.0", port)
    else:
        anyio.run(runners.run_stdio_async, server)
