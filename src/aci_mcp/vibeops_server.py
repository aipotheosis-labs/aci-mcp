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

if not os.getenv("VIBEOPS_API_KEY"):
    raise ValueError("VIBEOPS_API_KEY is not set")

server: Server = Server("aci-mcp-vibeops")


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
        types.Tool(
            name="ACI_GET_PROJECT_STATE",
            description="""
Get the current state of your project, including the GitLab, Vercel, and Supabase
deployments. Always first call this tool to get the state of your project, you would
need to know the state of your project to execute other functions using the
aci_execute_function tool.

Remember to run this tool every once in a while to get the latest state of your project
or after you have executed any function that may alter the state of your project.
""",
            inputSchema={
                "type": "object",
                "properties": {},
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

    try:
        if name == aci_search_functions["name"]:
            if not arguments.get("intent"):  # The intent cannot be ""
                return [
                    types.TextContent(
                        type="text",
                        text="Intent is required",
                    )
                ]
            async with httpx.AsyncClient(base_url=VIBEOPS_BASE_URL) as client:
                response = await client.get(
                    "/api/v1/functions/search",
                    headers={"Authorization": f"Bearer {os.getenv('VIBEOPS_API_KEY')}"},
                    params={"intent": arguments["intent"]},
                    timeout=10,
                )
                response.raise_for_status()  # Raise exception for HTTP errors
                return [types.TextContent(type="text", text=response.text)]
        elif name == aci_execute_function["name"]:
            if (
                (arguments.get("function_name") is None)
                or (
                    arguments.get("function_arguments") is None
                )  # function_arguments can be {} but not None
            ):
                return [
                    types.TextContent(
                        type="text",
                        text="Function name and function arguments are required",
                    )
                ]
            async with httpx.AsyncClient(base_url=VIBEOPS_BASE_URL) as client:
                response = await client.post(
                    f"/api/v1/functions/{arguments['function_name']}/execute",
                    headers={"Authorization": f"Bearer {os.getenv('VIBEOPS_API_KEY')}"},
                    json={"function_input": arguments["function_arguments"]},
                    timeout=30,
                )
                response.raise_for_status()  # Raise exception for HTTP errors
                return [types.TextContent(type="text", text=response.text)]
        elif name == "ACI_GET_PROJECT_STATE":
            async with httpx.AsyncClient(base_url=VIBEOPS_BASE_URL) as client:
                response = await client.get(
                    "/api/v1/projects/state",
                    headers={"Authorization": f"Bearer {os.getenv('VIBEOPS_API_KEY')}"},
                )
                response.raise_for_status()  # Raise exception for HTTP errors
                project_states = response.json()
                prompt = f"""
We have already created a GitLab project, Vercel project, and Supabase
project for you. The GitLab project is already linked to the Vercel
project. Any code pushed to the GitLab project will be automatically
deployed to the Vercel project. Test your code locally before pushing
to the GitLab project. You should use the access token returned below
to push the code to your GitLab project.

Here's the current state of your project:
GitLab: {project_states["gitlab"]}
Vercel: {project_states["vercel"]}
Supabase: {project_states["supabase"]}
                """
                # TODO: instruct the LLM to check Vercel deployment status once those
                # functions are integrated.
                return [types.TextContent(type="text", text=prompt)]
        else:
            return [types.TextContent(type="text", text="Not implemented")]

    except httpx.HTTPStatusError as e:
        return [
            types.TextContent(
                type="text",
                text=f"HTTP error {e.response.status_code}: {e.response.text}",
            )
        ]
    except httpx.TimeoutException:
        return [
            types.TextContent(
                type="text",
                text="Request timed out",
            )
        ]
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
