from httpx import AsyncClient
from src.core.settings import settings
from src.core.mcp.client import MCPClient

GHL = {"client": None, "catalog": None, "mcp_tools": None}

async def initialize_ghl_operations():
    
    client = MCPClient(
        http=AsyncClient(
            headers={
                "Accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {settings.GHL_PIT}",
                "locationId": settings.GHL_LOCATION_ID
            }
        ),
        url="https://services.leadconnectorhq.com/mcp/"
    )

    await client.initialize()

    GHL["client"] = client

    def trim_description(description: str):
        return description.split("Capabilities")[0].strip()

    tool_list = await client.list_tools()
    GHL["mcp_tools"] = {tool["name"]: tool for tool in tool_list}

    tools = {tool["name"]: trim_description(tool["description"]) for tool in tool_list}
    GHL["catalog"] = tools


def catalog_text() -> str:
    """One line per operation -- what the orchestrator sees in its system prompt."""
    return "\n".join(f"{name}: {desc}" for name, desc in GHL["catalog"].items())
    


async def describe_operation(operation_name: str):
    if GHL["mcp_tools"] is None:
        await initialize_ghl_operations()

    tool = GHL["mcp_tools"].get(operation_name)

    if not tool:
        return (
            f"Unknown operation '{operation_name}'. "
            f"Valid names: {', '.join(GHL['mcp_tools'])}"
        )

    return {"name": tool["name"], "parameters": tool["inputSchema"]}


async def execute_ghl_operation(tool_name: str, arguments: dict | None = None):
    if GHL["client"] is None:
        await initialize_ghl_operations()

    result = await GHL["client"].call_tool(name=tool_name, arguments=arguments or {})

    if result.is_error:
        return f"Operation failed: {result.text}"

    return result.text
    

    




