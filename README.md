# MCP servers powered by [ACI.dev](https://aci.dev)

> [!IMPORTANT]
> This README only covers basic development guide. For full documentation and tutorials on ACI.dev MCP servers please visit [aci.dev docs](https://aci.dev/docs/mcp-servers/introduction).

## Table of Contents

- [MCP servers powered by ACI.dev](#mcp-servers-powered-by-acidev)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Run MCP Servers Locally](#run-mcp-servers-locally)
  - [Integration with MCP Clients](#integration-with-mcp-clients)
  - [Docker](#docker)
  - [Debugging](#debugging)

## Overview

This package provides three Model Context Protocol (MCP) servers for accessing [ACI.dev](https://aci.dev) managed functions (tools):

- `aci-mcp-apps`: An MCP server that provides direct access to functions (tools) from specified apps
   <img src="./assets/apps-mcp-server-diagram.svg" alt="Apps Server"/>
- `aci-mcp-unified`: An MCP server that provides two meta functions (tools) (`ACI_SEARCH_FUNCTIONS` and `ACI_EXECUTE_FUNCTION`) to discover and execute **ALL** functions (tools) available on [ACI.dev](https://platform.aci.dev)
   <img src="./assets/unified-mcp-server-diagram.svg" alt="Unified Server">
- `aci-mcp-vibeops`: An MCP server that provides access to vibeops.aci.dev, which is a AI platform managing all the DevOps tools and workflows.

> [!IMPORTANT]
> For detailed explanation and tutorials on the MCP servers please visit [aci.dev docs](https://aci.dev/docs/mcp-servers/introduction).

## Run MCP Servers Locally

The package is published to PyPI, so you can run it directly using `uvx`:

```bash
# Install uv if you don't have it already
curl -sSf https://install.pypa.io/get-pip.py | python3 -
pip install uv
```

```bash
$ uvx aci-mcp --help
Usage: aci-mcp [OPTIONS] COMMAND [ARGS]...

  Main entry point for the package.

Options:
  --help  Show this message and exit.

Commands:
  apps-server     Start the apps-specific MCP server to access tools...
  unified-server  Start the unified MCP server with unlimited tool access.
  vibeops-server  Start the VibeOps MCP server to access VibeOps-managed tools.
```

## Integration with MCP Clients

See the [Unified MCP Server](https://www.aci.dev/docs/mcp-servers/unified-server#integration-with-mcp-clients) and [Apps MCP Server](https://www.aci.dev/docs/mcp-servers/apps-server#integration-with-mcp-clients) sections for more information on how to configure the MCP servers with different MCP clients.

For the VibeOps MCP server, you'll need to provide a `VIBEOPS_API_KEY` environment variable when configuring your MCP client.
<!-- TODO: add VibeOps MCP server to aci.dev/docs -->

## Docker

```bash
# Build the image
docker build -t aci-mcp .

# Run the unified server
docker run --rm -i -e ACI_API_KEY=<ACI_API_KEY> aci-mcp unified-server --linked-account-owner-id <LINKED_ACCOUNT_OWNER_ID>

# Run the apps server
docker run --rm -i -e ACI_API_KEY=<ACI_API_KEY> aci-mcp apps-server --apps <APP1,APP2,...> --linked-account-owner-id <LINKED_ACCOUNT_OWNER_ID>

# Run the VibeOps server
docker run --rm -i -e VIBEOPS_API_KEY=<VIBEOPS_API_KEY> aci-mcp vibeops-server
```

## Debugging

You can use the MCP inspector to debug the server:

```bash
# For unified server
npx @modelcontextprotocol/inspector uvx aci-mcp unified-server --linked-account-owner-id <LINKED_ACCOUNT_OWNER_ID>

# For apps server
npx @modelcontextprotocol/inspector uvx aci-mcp apps-server --apps "BRAVE_SEARCH,GMAIL" --linked-account-owner-id <LINKED_ACCOUNT_OWNER_ID>

# For VibeOps server
npx @modelcontextprotocol/inspector uvx aci-mcp vibeops-server
```

Running `tail -n 20 -f ~/Library/Logs/Claude/mcp*.log` will show the logs from the server and may help you debug any issues.
