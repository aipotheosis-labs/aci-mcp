import os

import click

from .common import validators


@click.group()
def main():
    """Main entry point for the package."""
    pass


@main.command(name="apps-server")
@click.option(
    "--apps",
    required=True,
    type=str,
    help="comma separated list of apps of which to use the functions",
)
@click.option(
    "--linked-account-owner-id",
    required=True,
    type=str,
    help="the owner id of the linked accounts to use for the tool calls. You'll need to create the linked accounts on platform.aci.dev",
)
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="Transport type",
)
@click.option("--port", default=8000, help="Port to listen on for SSE")
def start_apps_server(apps: str, linked_account_owner_id: str, transport: str, port: int) -> int:
    """Start the apps-specific MCP server to access tools under specific apps."""
    apps_list = [app.strip() for app in apps.split(",")]
    if not apps_list:
        raise click.UsageError("At least one app is required")
    from .apps_server import start

    validators.validate_api_key(os.getenv("ACI_API_KEY"))

    return start(apps_list, linked_account_owner_id, transport, port)


@main.command(name="unified-server")
@click.option(
    "--allowed-apps-only",
    is_flag=True,
    default=False,
    help="Limit the functions (tools) search to only the allowed apps that are accessible to this agent. (identified by ACI_API_KEY)",
)
@click.option(
    "--linked-account-owner-id",
    required=True,
    type=str,
    help="the owner id of the linked account to use for the tool calls",
)
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="Transport type",
)
@click.option("--port", default=8000, help="Port to listen on for SSE")
def start_unified_server(
    allowed_apps_only: bool, linked_account_owner_id: str, transport: str, port: int
) -> None:
    """Start the unified MCP server with unlimited tool access."""
    from .unified_server import start

    validators.validate_api_key(os.getenv("ACI_API_KEY"))

    return start(allowed_apps_only, linked_account_owner_id, transport, port)


@main.command(name="vibeops-server")
def start_vibeops_server() -> None:
    """Start the vibeops MCP server with default settings."""
    from .vibeops_server import start

    validators.validate_api_key(os.getenv("VIBEOPS_API_KEY"))

    return start(
        transport="stdio",
        port=8000,
    )
