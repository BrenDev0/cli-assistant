from httpx import AsyncClient
from src.core.settings import settings
from src.core.mcp.client import MCPClient

GHL = {"client": None, "mcp_tools": None}


WORKFLOW = """GoHighLevel is reached through three tools, not a fixed list of operations.
There is no catalog to browse and no way to list what exists: the server indexes the whole
GHL public API and answers searches against it, so searching is the only way to find out
what is available.

1. SearchGhlOperations -- describe what you want in plain language and get back matching
   operationIds with their method, path, required scopes, and whether each one reads,
   writes, deletes, or moves money. Every GHL task starts here. An operationId that did
   not come from a search result does not exist; guessing one wastes a call and teaches
   you nothing.
2. DescribeGhlOperation -- the exact parameter and body contract for one operationId.
   Required before any operation that takes a request body.
3. ExecuteGhlOperation -- run it. For anything that is not a plain read, run it once with
   dry_run=True, check the preview, then run it for real.

The index matches on wording, not meaning, so a plain-language query can rank loosely
related operations above the one you want -- 'find a contact by email' surfaces
get-duplicate-contact and get-email-campaign. Read the method and path of each result
rather than trusting the order. If nothing fits, search again using the vocabulary GHL
itself uses, or pass domains (['contacts'], ['conversations'], ['voice-ai']) to constrain
it. Two or three well-aimed searches, not a dozen rephrasings.

A search that keeps returning nothing means the connection's granted scopes do not cover
that area, not necessarily that the operation does not exist. Say so plainly."""


async def initialize_ghl_operations():
    """Open the MCP connection, or say plainly that it cannot be opened.

    The server accepts `initialize` without checking the token, so a missing or wrong one
    is not caught here -- it surfaces as a 401 on the first real operation. Checking for
    the keys up front is what turns "the token is not authorized for this scope" on some
    later turn into an answerable startup message.
    """
    if not settings.has_ghl():
        missing = [
            name for name, value in (
                ("GHL_PIT", settings.GHL_PIT),
                ("GHL_LOCATION_ID", settings.GHL_LOCATION_ID),
            ) if not value
        ]
        raise RuntimeError(
            f"{' and '.join(missing)} "
            f"{'is' if len(missing) == 1 else 'are'} not set -- add "
            f"{'it' if len(missing) == 1 else 'them'} to your .env to use the "
            f"GoHighLevel tools."
        )

    client = MCPClient(
        http=AsyncClient(
            headers={
                "Accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {settings.GHL_PIT}",
                "locationId": settings.GHL_LOCATION_ID
            }
        ),
        url="https://services.leadconnectorhq.com/mcp/v2"
    )

    await client.initialize()

    GHL["client"] = client

    tool_list = await client.list_tools()
    GHL["mcp_tools"] = {tool["name"]: tool for tool in tool_list}


def catalog_text() -> str:
    """What the orchestrator sees in its system prompt. A workflow, not a catalog --
    v2 has no operation list to show."""
    return WORKFLOW


async def _call(name: str, arguments: dict) -> str:
    """One path to the MCP server for all four tools, so connection setup, error shape and
    the lazy re-initialise are handled once rather than per tool."""
    if GHL["client"] is None:
        await initialize_ghl_operations()

    if name not in GHL["mcp_tools"]:
        return (
            f"The GHL server does not expose a '{name}' tool. It exposes: "
            f"{', '.join(GHL['mcp_tools'])}."
        )

    # None is "not supplied", which is not the same as an explicit null the server would
    # have to interpret -- drop those rather than sending them.
    payload = {k: v for k, v in arguments.items() if v is not None}

    result = await GHL["client"].call_tool(name=name, arguments=payload)

    if result.is_error:
        return f"{name} failed: {result.text}"

    return result.text


async def search_ghl_operations(
    query: str,
    domains: list[str] | None = None,
    kind: str | None = None,
    limit: int | None = None,
) -> str:
    return await _call(
        "search_operations",
        {"query": query, "domains": domains, "kind": kind, "limit": limit},
    )


async def describe_operation(operation_id: str) -> str:
    return await _call("describe_operation", {"operationId": operation_id})


async def execute_ghl_operation(
    operation_id: str,
    params: dict | None = None,
    dry_run: bool = False,
    reason: str = "",
    idempotency_key: str | None = None,
    location_id: str | None = None,
) -> str:
    return await _call(
        "execute_operation",
        {
            "operationId": operation_id,
            "params": params or {},
            "dryRun": dry_run or None,
            "reason": reason or None,
            "idempotencyKey": idempotency_key,
            "locationId": location_id,
        },
    )


# The server also exposes list_locations, but it answers 500 "dependencies are not
# configured" on a private-integration-token connection -- it is built for OAuth
# connections that can span sub-accounts. Not wired up as a tool: one that can only ever
# fail costs a tool schema in every request and teaches the model nothing when it is
# called. The connection's bound location is injected server-side anyway.
