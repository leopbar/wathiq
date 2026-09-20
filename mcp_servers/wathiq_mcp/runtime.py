"""Shared runtime for the four Wathiq MCP servers.

Every server here is a real MCP server built with the official Python SDK, speaking streamable
HTTP over the Compose network. They are separate processes on purpose: that is what makes
"least privilege" true rather than decorative. The core-banking server can write; the others
cannot; and a node of the agent graph is given the address of only the servers it needs.

Each server also exposes a plain `/healthz` route so Docker can tell whether it is up without
speaking MCP.
"""

from __future__ import annotations

import logging
import os

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s | %(message)s"


def build_server(name: str, title: str, instructions: str, version: str = "1.0.0") -> MCPServer:
    """One MCP server, with its health route already attached."""
    server = MCPServer(
        name=name,
        title=title,
        instructions=instructions,
        version=version,
    )

    @server.custom_route("/healthz", methods=["GET"])
    async def healthz(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "server": name, "version": version})

    return server


def serve(server: MCPServer, default_port: int) -> None:
    """Run the server over streamable HTTP.

    The app is built explicitly rather than through `server.run(...)` so the host, the port and
    the transport security settings are all visible in one place.
    """
    logging.basicConfig(
        level=os.environ.get("WATHIQ_LOG_LEVEL", "INFO").upper(), format=LOG_FORMAT
    )
    port = int(os.environ.get("MCP_PORT", default_port))
    host = os.environ.get("MCP_HOST", "0.0.0.0")

    # DNS-rebinding protection stays ON. Inside Compose the client reaches us by service
    # name, so that name has to be on the allowlist — which is set per service in
    # compose.yaml, deliberately, rather than turned off with a wildcard.
    allowed = [
        entry.strip()
        for entry in os.environ.get("MCP_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
        if entry.strip()
    ]
    host_patterns = [pattern for entry in allowed for pattern in (entry, f"{entry}:*")]

    app = server.streamable_http_app(
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=host_patterns,
            # No browser ever talks to these servers, so no origin is expected.
            allowed_origins=[],
        ),
    )
    logging.getLogger(server.name).info("serving MCP on http://%s:%s/mcp", host, port)
    uvicorn.run(app, host=host, port=port, log_level="warning")
