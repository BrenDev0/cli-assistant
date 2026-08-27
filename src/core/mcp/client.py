import json
from dataclasses import dataclass
from uuid import uuid4
import httpx

# Newest revision this client knows how to speak. Only a proposal — the server
# answers with the version it will actually use, which is what we honor.
LATEST_PROTOCOL_VERSION = "2025-06-18"


@dataclass
class ToolResult:
    text: str
    is_error: bool


class MCPError(Exception):
    """A protocol-level failure — bad method, malformed request, transport error.

    Tool *execution* failures are not this; they come back as ToolResult(is_error=True)
    so the model can read them and react.
    """

class MCPClient:
    """Streamable-HTTP MCP client. Knows nothing about any particular server."""

    def __init__(
        self,
        url: str,
        headers: dict[str, str],
        client_name: str = "cli-assistant",
        client_version: str = "0.1.0",
        protocol_version: str = LATEST_PROTOCOL_VERSION,
    ):
        self._url = url
        # Accept goes last so a caller can't accidentally override it — this server
        # 406s unless both media types are named explicitly.
        self._headers = {
            **headers,
            "Accept": "application/json, text/event-stream",
        }
        self._client_name = client_name
        self._client_version = client_version
        self._proposed_version = protocol_version

        self._http: httpx.AsyncClient | None = None
        self._tools: list[dict] | None = None

        # Negotiated at initialize() — the version the *server* chose, which may
        # be older than the one we proposed. Read this, never _proposed_version.
        self.protocol_version: str | None = None
        self.server_capabilities: dict = {}
        self.server_info: dict = {}

    async def __aenter__(self):
        self._http = httpx.AsyncClient(headers=self._headers, timeout=30.0)
        await self.initialize()
        return self

    async def __aexit__(self, *exc):
        if self._http:
            await self._http.aclose()
            self._http = None


    async def _rpc(self, method: str, params: dict) -> dict:
        if self._http is None:
            raise MCPError("client not open — use `async with MCPClient(...)`")

        body = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": method,
            "params": params,
        }

        response = await self._http.post(self._url, json=body)

        # Parse before checking the status: servers routinely pair a non-2xx with a
        # perfectly good JSON-RPC error body, and that message is far more useful
        # than the status code. raise_for_status() is the fallback, not the gate.
        payload = _parse_sse(response.text)

        if payload is not None and "error" in payload:
            err = payload["error"]
            raise MCPError(f"{method} failed [{err.get('code')}]: {err.get('message')}")

        response.raise_for_status()

        if payload is None:
            raise MCPError(
                f"no JSON-RPC payload in response to {method!r} "
                f"(status {response.status_code}): {response.text[:300]}"
            )

        return payload["result"]

    async def initialize(self) -> None:
        result = await self._rpc(
            "initialize",
            {
                "protocolVersion": self._proposed_version,
                "capabilities": {},
                "clientInfo": {
                    "name": self._client_name,
                    "version": self._client_version,
                },
            },
        )
        # The server picks the version, not us. Record what it chose.
        self.protocol_version = result.get("protocolVersion")
        self.server_capabilities = result.get("capabilities", {})
        self.server_info = result.get("serverInfo", {})

    async def list_tools(self) -> list[dict]:
        """Fetch the tool catalog. Cached — servers without a `listChanged`
        capability never notify us of changes, so one fetch is enough."""
        if self._tools is None:
            result = await self._rpc("tools/list", {})
            self._tools = result.get("tools", [])
        return self._tools

    async def call_tool(self, name: str, arguments: dict) -> ToolResult:
        result = await self._rpc(
            "tools/call", {"name": name, "arguments": arguments}
        )

        text = "\n".join(
            block.get("text", "")
            for block in result.get("content", [])
            if block.get("type") == "text"
        )
        return ToolResult(text=text, is_error=bool(result.get("isError")))


def _parse_sse(raw: str) -> dict | None:
    """Pull the JSON off the first `data:` line of an SSE frame."""
    for line in raw.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return None