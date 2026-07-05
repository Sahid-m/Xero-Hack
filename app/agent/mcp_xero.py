"""Xero remote MCP — https://builders.xero.com/beta/mcp"""

from __future__ import annotations

import logging
import re

import ai
from ai.agents.mcp.client import get_http_tools

from app.config import get_settings
from app.xero_client import ensure_token, is_connected

logger = logging.getLogger(__name__)

_WRITE_TOOL = re.compile(
    r"^(xero_)?(create|update|delete|void|email|send|post|record|approve)",
    re.I,
)

# Session-only setup tools (no Xero API — stored in Voca session)
from app.agent.tools.xero import (
    SETUP_TOOLS,
    create_and_send_invoice,
    reconcile_invoice_payment,
    record_supplier_bill,
    send_payment_reminder,
)
from app.agent.tools.xero_queries import find_reconciliation_matches

# MCP cannot authorise invoices, email payment reminders, or match/record
# reconciliation payments — keep these local tools.
GAP_TOOLS: list[ai.AgentTool] = [
    create_and_send_invoice,
    record_supplier_bill,
    send_payment_reminder,
    find_reconciliation_matches,
    reconcile_invoice_payment,
]


async def get_xero_mcp_tools(connection_id: str) -> list[ai.AgentTool]:
    """Load tools from Xero's hosted MCP server using the user's OAuth access token."""
    if not is_connected(connection_id):
        return []

    settings = get_settings()
    url = settings.xero_mcp_url.rstrip("/")
    token = ensure_token(connection_id)
    access_token = token.get("access_token")
    if not access_token:
        return []

    try:
        tools = await get_http_tools(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            tool_prefix="xero",
        )
        logger.info("Loaded %d Xero MCP tools for connection %s", len(tools), connection_id[:8])
        return tools
    except Exception:
        logger.exception("Failed to load Xero MCP tools from %s", url)
        return []


def mark_write_tools_for_approval(tools: list[ai.AgentTool]) -> list[ai.AgentTool]:
    """Flag MCP write tools so the UI shows approve/reject (same as legacy @ai.tool)."""
    marked: list[ai.AgentTool] = []
    for agent_tool in tools:
        name = agent_tool.tool.name
        if _WRITE_TOOL.search(name):
            agent_tool = ai.AgentTool(
                tool=agent_tool.tool.model_copy(update={"require_approval": True}),
                fn=agent_tool.fn,
            )
        marked.append(agent_tool)
    return marked


async def build_agent_tools(connection_id: str | None) -> list[ai.AgentTool]:
    """Setup interview tools + Xero MCP when connected + local gap tools for send/chase."""
    tools: list[ai.AgentTool] = list(SETUP_TOOLS)
    if connection_id and is_connected(connection_id):
        mcp = await get_xero_mcp_tools(connection_id)
        tools.extend(mark_write_tools_for_approval(mcp))
        tools.extend(GAP_TOOLS)
    return tools


async def build_agent(connection_id: str | None) -> ai.Agent:
    return ai.Agent(tools=await build_agent_tools(connection_id))
