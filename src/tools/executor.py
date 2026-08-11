import inspect
import asyncio

from .registry import TOOL_REGISTRY


async def executor(tool_name: str, params: dict):
    if tool_name not in TOOL_REGISTRY.keys():
        raise ValueError(f"tool {tool_name} not in registry")

    tool = TOOL_REGISTRY[tool_name]

    if inspect.iscoroutinefunction(tool):
        return await tool(**params)

    return await asyncio.to_thread(tool, **params)