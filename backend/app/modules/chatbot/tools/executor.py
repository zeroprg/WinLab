"""Policy-checked tool executor."""

from __future__ import annotations

from app.modules.chatbot.schemas import ToolCall, ToolResult
from app.modules.chatbot.tools.registry import ToolRegistry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def execute(self, call: ToolCall) -> ToolResult:
        tool = self.registry.get(call.name)
        if tool is None:
            return ToolResult(
                success=False,
                error_code="TOOL_NOT_FOUND",
                message=f"Tool '{call.name}' is not registered.",
            )

        if call.pii_scope != "none" and call.pii_scope != tool.pii_scope:
            return ToolResult(
                success=False,
                error_code="PII_SCOPE_MISMATCH",
                message="Requested PII scope does not match tool policy.",
            )

        return await tool.handler(call)

