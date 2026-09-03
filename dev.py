import asyncio
from src.tools.ghl.tools import GHL, initialize_ghl_operations
from httpx import AsyncClient
from src.core.settings import settings
from src.core.mcp.client import MCPClient


async def main():
    await initialize_ghl_operations()
    tools = GHL["mcp_tools"]
    for tool in tools.keys():
        print(tool)


if __name__ == "__main__":
    asyncio.run(main())