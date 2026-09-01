from typing import Any

from pydantic import BaseModel, Field


class DescribeGhlOperation(BaseModel):
    """Get the exact parameter names and types for a GoHighLevel operation.

    Always call this before ExecuteGhlOperation. GHL parameter names cannot be
    guessed from the operation name -- they must be read from this schema first.
    """
    operation_name: str = Field(description="Exact operation name from the GHL catalog, for example 'contacts_get-contact'")


class ExecuteGhlOperation(BaseModel):
    """Run a GoHighLevel operation and return the API response"""
    tool_name: str = Field(description="Exact operation name from the GHL catalog, for example 'contacts_get-contact'")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Parameters for the operation, taken from DescribeGhlOperation. Names are flat and "
            "prefixed by where they belong in the request: 'path_' for values in the URL path, "
            "'query_' for query-string filters, 'body_' for request-body fields. "
            "Example: {\"path_contactId\": \"ocQHyuzHvysMo5N5VsXc\"}"
        ),
    )
