"""Typed tool registry."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.modules.chatbot.schemas import ToolCall, ToolResult

ToolHandler = Callable[[ToolCall], Awaitable[ToolResult]]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    pii_scope: str
    description: str
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return sorted(self._tools)

