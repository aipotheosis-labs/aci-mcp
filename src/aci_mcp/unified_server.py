import json
import logging
import os

import anyio
import httpx
import mcp.types as types
from aci import ACI
from aci.meta_functions import ACIExecuteFunction, ACISearchFunctions
from aci.types.enums import FunctionDefinitionFormat
from mcp.server.lowlevel import Server

from .common import runners

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# TODO: We need the API key and server URL because we are using an endpoint in the aci.dev main
# server to do vector search on docs. In a future version, we might want to move the endpoint to
# the customer support bot server.
ACI_API_KEY = os.getenv("ACI_API_KEY", "")
if not ACI_API_KEY:
    raise ValueError(
        "ACI_API_KEY environment variable is not set. Please set it to your ACI API key."
    )

ACI_SERVER_URL = os.getenv("ACI_SERVER_URL", "https://api.aci.dev/v1")

ALLOWED_APPS_ONLY = False
LINKED_ACCOUNT_OWNER_ID = ""

aci_search_functions = ACISearchFunctions.to_json_schema(FunctionDefinitionFormat.ANTHROPIC)
aci_execute_function = ACIExecuteFunction.to_json_schema(FunctionDefinitionFormat.ANTHROPIC)
ACI_QUERY_DOCS_FUNCTION_NAME = "ACI_SEARCH_DOCS"

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


aci = ACI()
server: Server = Server("aci-mcp-unified")


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
        types.Tool(
            name=ACI_QUERY_DOCS_FUNCTION_NAME,
            description="Search for ACI.dev concepts, documentation,"
            " Python & TypeScript SDK documentation, and usage examples",
            inputSchema={
                "type": "object",
                "properties": {
                    "q": {
                        "type": "string",
                        "description": "The query to search for in the ACI documentation.",
                    },
                },
                "required": ["q"],
            },
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

    if name == ACI_QUERY_DOCS_FUNCTION_NAME:
        query = arguments.get("q", "")
        if not query or not isinstance(query, str) or not query.strip():
            return [
                types.TextContent(
                    type="text",
                    text="Error: Query parameter 'q' must be a non-empty string.",
                )
            ]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{ACI_SERVER_URL}/docs",
                    params={"q": query.strip()},
                    headers={"X-API-KEY": ACI_API_KEY},
                )

                if response.status_code != 200:
                    return [
                        types.TextContent(
                            type="text",
                            text=f"Error: API request failed with status {response.status_code}.",
                        )
                    ]

                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(response.json()),
                    )
                ]
        except httpx.TimeoutException:
            return [
                types.TextContent(
                    type="text",
                    text=(
                        "Error: Request timed out while querying documentation. "
                        "Please try again later."
                    ),
                )
            ]
        except httpx.RequestError as e:
            return [
                types.TextContent(
                    type="text",
                    text=(f"Error: Network error occurred while querying documentation: {str(e)}"),
                )
            ]
        except httpx.HTTPStatusError as e:
            return [
                types.TextContent(
                    type="text",
                    text=(
                        f"Error: HTTP error {e.response.status_code} occurred while querying "
                        "documentation."
                    ),
                )
            ]
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=(f"Error: An unexpected error occurred while querying docs: {str(e)}"),
                )
            ]

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
