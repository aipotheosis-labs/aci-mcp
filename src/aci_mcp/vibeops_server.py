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

VIBEOPS_BASE_URL = os.getenv("VIBEOPS_BASE_URL", "https://controller.aci.dev")

VIBEOPS_API_KEY = os.getenv("VIBEOPS_API_KEY", "")

if not VIBEOPS_API_KEY:
    raise ValueError("VIBEOPS_API_KEY is not set")

server: Server = Server("aci-mcp-vibeops")

SUPABASE_AUTH_SNIPPET = """
const getURL = () => {
  let url = process?.env?.NEXT_PUBLIC_VERCEL_URL || 'http://localhost:3000/'
  
  // Make sure to include `https://` when not localhost
  if (!url.startsWith('http')) {
    url = `https://${url}`
  }
  
  // Make sure to include a trailing `/`
  if (!url.endsWith('/')) {
    url = `${url}/`
  }
  
  return url
}

const { data, error } = await supabase.auth.signInWithOAuth({
  options: {
    redirectTo: getURL(),
  },
})
"""

aci_search_functions = ACISearchFunctions.to_json_schema(FunctionDefinitionFormat.ANTHROPIC)
aci_execute_function = ACIExecuteFunction.to_json_schema(FunctionDefinitionFormat.ANTHROPIC)

# TODO: Cursor's auto mode doesn't work well with MCP. (generating wrong type of parameters and
# the type validation logic is not working correctly). So temporarily we're removing the limit and
# offset parameters from the search function.
aci_search_functions["input_schema"]["properties"].pop("limit", None)
aci_search_functions["input_schema"]["properties"].pop("offset", None)

ALL_TOOLS: list[types.Tool] = []
ALL_TOOL_NAMES: set[str] = set()


def _set_up():
    """
    Set up global variables
    """
    global ALL_TOOLS

    with httpx.Client(base_url=VIBEOPS_BASE_URL) as client:
        response = client.get(
            "/v1/functions/search",
            headers={"X-API-KEY": VIBEOPS_API_KEY},
            params={"format": FunctionDefinitionFormat.ANTHROPIC.value},
            timeout=10,
        )
        response.raise_for_status()  # Raise exception for HTTP errors
        functions = response.json()
        for function in functions:
            ALL_TOOLS.append(
                types.Tool(
                    name=function["name"],
                    description=function["description"],
                    inputSchema=function["input_schema"],
                )
            )
            ALL_TOOL_NAMES.add(function["name"])


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools.
    """
    return [
        types.Tool(
            name="GET_PROJECT_STATE",
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
    ] + ALL_TOOLS


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
        if name == "GET_PROJECT_STATE":
            async with httpx.AsyncClient(base_url=VIBEOPS_BASE_URL) as client:
                response = await client.get(
                    "/v1/projects/self",
                    headers={"X-API-KEY": VIBEOPS_API_KEY},
                )
                response.raise_for_status()  # Raise exception for HTTP errors
                project_states = response.json()
                prompt = f"""
We have already created a GitLab project, Vercel project, and Supabase
project for you. The GitLab project is already linked to the Vercel
project. Any code pushed to the GitLab project will be automatically
deployed to the Vercel project. You should use the access token returned below
to push the code to your GitLab project (for example, you can add the git remote using
this command: `git remote add origin https://vibe:{project_states["gitlab"]["resource"]["resource_config"]["project_access_token"]}@gitlab.com/vibeops.infra-group/{project_states["gitlab"]["resource"]["resource_config"]["name"]}.git`).

Here's the current state of your project:
GitLab: {project_states["gitlab"]}
Vercel: {project_states["vercel"]}
Supabase: {project_states["supabase"]}

Best practices:
You are an expert in TypeScript, Node.js, Next.js App Router, React, Shadcn UI, Radix UI and Tailwind.

- Use the create-next-app CLI command to create a new Next.js project in the root folder. e.g. npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --turbopack
- Run `npm run build` before pushing the code.
- Check you have a .gitignore file before pushing the code.

Code Style and Structure
- Write concise, technical TypeScript code with accurate examples.
- Use functional and declarative programming patterns; avoid classes.
- Prefer iteration and modularization over code duplication.
- Use descriptive variable names with auxiliary verbs (e.g., isLoading, hasError).
- Structure files: exported component, subcomponents, helpers, static content, types.

Naming Conventions
- Use lowercase with dashes for directories (e.g., components/auth-wizard).
- Favor named exports for components.

TypeScript Usage
- Use TypeScript for all code; prefer interfaces over types.
- Avoid enums; use maps instead.
- Use functional components with TypeScript interfaces.

Syntax and Formatting
- Use the "function" keyword for pure functions.
- Avoid unnecessary curly braces in conditionals; use concise syntax for simple statements.
- Use declarative JSX.

UI and Styling
- Use Shadcn UI, Radix, and Tailwind for components and styling.
- Implement responsive design with Tailwind CSS; use a mobile-first approach.

Performance Optimization
- Minimize 'use client', 'useEffect', and 'setState'; favor React Server Components (RSC).
- Wrap client components in Suspense with fallback.
- Use dynamic loading for non-critical components.
- Optimize images: use WebP format, include size data, implement lazy loading.

Key Conventions
- Use 'nuqs' for URL search parameter state management.
- Optimize Web Vitals (LCP, CLS, FID).
- Limit 'use client':
- Favor server components and Next.js SSR.
- Use only for Web API access in small components.
- Avoid for data fetching or state management.

Follow Next.js docs for Data Fetching, Rendering, and Routing.

Important Notes:
If you're using Supabase Auth for login and signup, set a redirect URL to send users after they confirm their email. See the code snippet below for how to do this with the Supabase SDK.
you must set these part on your supabase project or find a way or set redirect url to your project.
{SUPABASE_AUTH_SNIPPET}
"""
                # TODO: instruct the LLM to check Vercel deployment status once those
                # functions are integrated.
                return [types.TextContent(type="text", text=prompt)]
        elif name in ALL_TOOL_NAMES:
            async with httpx.AsyncClient(base_url=VIBEOPS_BASE_URL) as client:
                response = await client.post(
                    f"/v1/functions/{name}/execute",
                    headers={"X-API-KEY": VIBEOPS_API_KEY},
                    json={"function_input": arguments},
                )
                response.raise_for_status()  # Raise exception for HTTP errors
                return [types.TextContent(type="text", text=response.text)]
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

    _set_up()

    if transport == "sse":
        anyio.run(runners.run_sse_async, server, "0.0.0.0", port)
    else:
        anyio.run(runners.run_stdio_async, server)
