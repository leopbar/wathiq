"""Calling the MCP tool servers, with least privilege enforced on this side too.

The four servers are separate processes (see `mcp_servers/`). This module is the only way the
agent reaches them, and it adds two things the servers cannot do for themselves:

**An allowlist per node.** A `ToolBroker` is created for one node of the graph and knows the
exact tool names that node may call. Asking for anything else raises before a request is made,
and the refusal is recorded. The servers already enforce separation by *existing separately* —
the investigator is never given the core-banking address — and this is the second lock: even
if a URL leaked into the wrong place, the broker would refuse the call.

**An honest record.** Every call, its arguments, how long it took, and whether it succeeded
goes into a `ToolCall` list that ends up in the case timeline. A reviewer can see exactly
which external checks were done, in what order, and what came back.

If a server is unreachable, the call fails and that failure is part of the record. Nothing
falls back to a local imitation of the tool — a check that did not happen must never look like
a check that passed.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from mcp import Client

from app.azure import monitor
from app.core.config import settings

logger = logging.getLogger(__name__)

# --- the tool catalogue --------------------------------------------------------
# server key -> (human name, setting attribute, whether it can write)
SERVERS: dict[str, tuple[str, str, bool]] = {
    "document_store": ("Document store", "mcp_document_store_url", False),
    "company_registry": ("Company registry (simulated)", "mcp_company_registry_url", False),
    "sanctions": ("Sanctions screening (simulated)", "mcp_sanctions_url", False),
    "core_banking": ("Core banking (simulated)", "mcp_core_banking_url", True),
}

# Which tools each node of the graph is allowed to call. This table is the least-privilege
# policy, in one readable place.
#
# Note what the investigator does NOT have: `core_banking.post_kyc_refresh`. The investigator
# reads the world; only the posting step (M4) writes to it, and only after a human approved.
NODE_TOOLS: dict[str, dict[str, list[str]]] = {
    "investigator": {
        "company_registry": ["lookup_by_license", "search_by_name", "reconcile_names"],
        "sanctions": ["screen_name"],
        "document_store": ["read_document", "find_in_document", "list_case_documents"],
    },
    "critic": {
        "document_store": ["find_in_document"],
    },
    # Wired in M4, when posting happens after approval.
    "post": {
        "core_banking": ["get_customer", "post_kyc_refresh", "get_posting"],
    },
}


class ToolNotAllowed(RuntimeError):
    """Raised when a node asks for a tool its allowlist does not contain."""


@dataclass(slots=True)
class ToolCall:
    """One attempt to use a tool. Recorded whether it worked or not."""

    server: str
    tool: str
    arguments: dict[str, Any]
    ok: bool
    duration_ms: int
    result: dict[str, Any] | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def summary(self) -> str:
        status = "ok" if self.ok else f"failed: {self.error}"
        return f"{self.server}.{self.tool} → {status} ({self.duration_ms} ms)"


@dataclass
class ToolBroker:
    """The tools one node may use, plus the record of what it used."""

    node: str
    allowed: dict[str, list[str]] = field(default_factory=dict)
    calls: list[ToolCall] = field(default_factory=list)

    @classmethod
    def for_node(cls, node: str) -> ToolBroker:
        return cls(node=node, allowed=NODE_TOOLS.get(node, {}))

    # -- policy ---------------------------------------------------------------

    def may_call(self, server: str, tool: str) -> bool:
        return tool in self.allowed.get(server, [])

    def url_for(self, server: str) -> str:
        attribute = SERVERS.get(server, ("", "", False))[1]
        return str(getattr(settings, attribute, "")) if attribute else ""

    def available(self, server: str) -> bool:
        """Configured and allowed for this node — not the same as 'currently reachable'."""
        return bool(self.url_for(server)) and bool(self.allowed.get(server))

    # -- calling --------------------------------------------------------------

    async def call(self, server: str, tool: str, **arguments: Any) -> ToolCall:
        """Call one tool. Never raises for a server-side failure — it records it."""
        if not self.may_call(server, tool):
            raise ToolNotAllowed(
                f"node {self.node!r} may not call {server}.{tool}; "
                f"allowed here: {sorted(self.allowed.get(server, []))}"
            )

        url = self.url_for(server)
        started = time.perf_counter()
        if not url:
            call = ToolCall(
                server=server,
                tool=tool,
                arguments=arguments,
                ok=False,
                duration_ms=0,
                error="server not configured",
            )
            self.calls.append(call)
            return call

        try:
            # One span per tool call (M6). The server and tool are recorded, the arguments are
            # not: a tool call carries customer values, and a trace leaves the building.
            with monitor.span(
                f"mcp.{server}.{tool}", tool_server=server, tool_name=tool, node=self.node
            ):
                payload = await self._invoke(url, tool, arguments)
            call = ToolCall(
                server=server,
                tool=tool,
                arguments=arguments,
                ok=True,
                duration_ms=int((time.perf_counter() - started) * 1000),
                result=payload,
            )
        except Exception as exc:  # any transport failure is a failed check, not a crash
            logger.warning("MCP call %s.%s failed: %s", server, tool, exc)
            call = ToolCall(
                server=server,
                tool=tool,
                arguments=arguments,
                ok=False,
                duration_ms=int((time.perf_counter() - started) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )

        self.calls.append(call)
        return call

    async def _invoke(self, url: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """One request/response over streamable HTTP, using the official MCP client."""
        async with Client(url, read_timeout_seconds=settings.mcp_timeout_seconds) as client:
            result = await client.call_tool(tool, arguments)

        if result.is_error:
            text = _first_text(result) or "tool reported an error"
            raise RuntimeError(text)

        if result.structured_content is not None:
            return dict(result.structured_content)
        text = _first_text(result)
        if text is None:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}
        return parsed if isinstance(parsed, dict) else {"result": parsed}

    # -- record ---------------------------------------------------------------

    def record(self) -> list[dict[str, Any]]:
        return [call.as_dict() for call in self.calls]

    @property
    def succeeded(self) -> int:
        return sum(1 for call in self.calls if call.ok)


def _first_text(result: Any) -> str | None:
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            return str(text)
    return None


def describe_servers() -> list[dict[str, Any]]:
    """The tool catalogue and the least-privilege matrix, for the Settings screen."""
    rows: list[dict[str, Any]] = []
    for key, (name, attribute, writes) in SERVERS.items():
        nodes = sorted(node for node, tools in NODE_TOOLS.items() if tools.get(key))
        tools = sorted({tool for tools in NODE_TOOLS.values() for tool in tools.get(key, [])})
        rows.append(
            {
                "key": key,
                "name": name,
                "url_configured": bool(getattr(settings, attribute, "")),
                "can_write": writes,
                "tools": tools,
                "used_by_nodes": nodes,
            }
        )
    return rows
