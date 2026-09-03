from typing import Any, Literal

from pydantic import BaseModel, Field


class SearchGhlOperations(BaseModel):
    """Find a GoHighLevel operation by describing what you want to do in plain language.

    The v2 server does not publish a catalog of operations -- it indexes the whole GHL
    public API and answers queries against it, so this is the ONLY way to discover what is
    available. Always start here. Never guess an operationId; a guessed one simply is not
    found, and the error tells you nothing about what the real one is.

    Each result carries the operationId, method and path, requiredScopes, whether it takes
    a request body, and whether it is a read, a write, a delete, or moves money."""
    query: str = Field(description="What you are trying to do, in plain language -- 'find a contact by email', 'create a conversation AI agent', 'list pipelines'")
    domains: list[str] | None = Field(default=None, description="Optional domains to constrain the search, for example ['contacts'] or ['conversations']. Leave unset unless a first search returned results from the wrong area.")
    kind: Literal["read", "write", "delete", "money_movement"] | None = Field(
        default=None,
        description="Optional filter. Use 'read' when you only need to look something up -- it keeps write and money-moving operations out of the results entirely.",
    )
    limit: int | None = Field(default=None, ge=1, le=50, description="Maximum results (1-50). Defaults to the server's own limit.")


class DescribeGhlOperation(BaseModel):
    """Get the exact request contract for one operationId returned by SearchGhlOperations.

    Returns the path and query parameters, the request body fields, a sanitised example
    payload, the required scopes, and safety metadata. Call this before ExecuteGhlOperation
    whenever the operation takes a request body or its parameters are not obvious -- the
    field names cannot be guessed from the operation name."""
    operation_id: str = Field(description="Exact operationId from a SearchGhlOperations result, for example 'update-association'")


class ExecuteGhlOperation(BaseModel):
    """Run a GoHighLevel operation and return the API response.

    The server applies authorisation, the API version, scope and permission checks, and
    tenant isolation itself -- you supply only the operation and its parameters.

    This acts on the user's live CRM. For anything that creates, changes, deletes, or moves
    money, run it once with dry_run=True first, check the preview, and only then run it for
    real. Never send a write whose body you have not confirmed with DescribeGhlOperation."""
    operation_id: str = Field(description="Exact operationId from a SearchGhlOperations result")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Parameters for the operation. Either grouped -- "
            "{\"path\": {...}, \"query\": {...}, \"body\": {...}} -- or flat, in which case the "
            "server maps known field names to the right place. Take the names from "
            "DescribeGhlOperation rather than guessing them."
        ),
    )
    dry_run: bool = Field(
        default=False,
        description="Preview the request and the parameters you supplied without actually running it upstream. Use this before every write, delete, or money-moving operation.",
    )
    reason: str = Field(default="", description="Short user-facing reason for the operation, shown in GoHighLevel's audit trail. Give one for any write.")
    idempotency_key: str | None = Field(default=None, description="Optional key that makes a retried write apply once rather than twice. Supply a stable value when retrying a write that may already have gone through.")
    location_id: str | None = Field(default=None, description="Sub-account to act on. Omit on a single-location connection, which is the normal case here -- the bound location is used automatically.")
