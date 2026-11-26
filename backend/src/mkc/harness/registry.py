"""The default tool registry (MKC-14.2). Skeleton: the tools come next."""

from mkc.harness.tools import Tool, ToolRegistry

ITEM_TOOLS: tuple[Tool, ...] = ()
RUN_OPERATIONS: tuple[Tool, ...] = ()


def default_registry() -> ToolRegistry:
    return ToolRegistry(item=ITEM_TOOLS, run=RUN_OPERATIONS)
