from typing import Any, Literal

from pydantic import BaseModel, Field


class FetchGhlDataset(BaseModel):
    """Pull every page of a GoHighLevel READ operation into a file on disk, and get back a
    description of the data rather than the data itself.

    USE THIS FOR ANY QUESTION ABOUT MORE THAN A HANDFUL OF RECORDS -- counts, totals,
    breakdowns, trends, "how many", "what share of", anything per-month or per-stage.
    ExecuteGhlOperation returns one page, usually 20 rows out of thousands, straight into
    your context. Answering a counting question from that has two failure modes and both
    produce a confident wrong number: you are working from a fraction of the records, and
    you are adding up values by reading them rather than by counting them. This tool
    removes both. It pages to the end, writes one JSON object per line, and hands you row
    counts, field names, null rates and value ranges that were computed over the file.

    Keep using ExecuteGhlOperation for single records ("what is this contact's email"),
    for anything that writes, and for reads where you genuinely only want the newest few.

    What comes back is a manifest: the path to the rows, the row count against the total
    GHL reported, whether the fetch is complete, and a per-field profile. The rows never
    enter your context, so read the profile to decide what to ask, then query the file.
    If the manifest says Complete: NO, the file is a partial pull -- say so in whatever
    you report and never describe it as the full set.

    Fetches are cached per day under the name you give, so asking a second question about
    the same dataset costs no API calls. Pass refresh=True when you need it re-pulled."""

    name: str = Field(
        description=(
            "Short name for this dataset, used as the folder name -- 'contacts', "
            "'won-opportunities-q3', 'conversations'. Reuse the same name for the same "
            "query to hit the day's cache; use a different one for a different query, "
            "since a name holding one query's rows must not be asked another's question."
        )
    )
    operation_id: str = Field(
        description=(
            "Exact operationId from a SearchGhlOperations result, and it must be a read. "
            "Prefer the search/list form of an operation -- 'search-contacts-advanced' "
            "rather than 'get-contact'. Search with kind='read' to find it."
        )
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Filters and sort for the operation, in the same grouped shape "
            "ExecuteGhlOperation takes: {\"query\": {...}} or {\"body\": {...}}. Take the "
            "field names from DescribeGhlOperation. Do NOT set page size, page number, or "
            "any cursor (limit, pageLimit, page, searchAfter, startAfter, "
            "startAfterDate) -- paging is handled for you and a value here will fight it. "
            "locationId is filled in automatically where the operation needs one."
        ),
    )
    max_rows: int = Field(
        default=5000,
        ge=1,
        le=50000,
        description=(
            "Safety ceiling on the fetch. Raise it when GHL reports a total above it -- "
            "the manifest will say the fetch is incomplete if this is what stopped it. "
            "Lower it only when a sample really is enough, and remember the manifest will "
            "then correctly refuse to call the result complete."
        ),
    )
    fields: list[str] | None = Field(
        default=None,
        description=(
            "Top-level fields to keep, dropping the rest. Leave unset to keep everything, "
            "which is usually right -- a field you did not keep is a question you cannot "
            "ask later without re-fetching. Narrow it only for very large pulls."
        ),
    )
    pagination: Literal["auto", "searchAfter", "startAfterDate", "startAfter", "page"] = Field(
        default="auto",
        description=(
            "Leave on 'auto'. It reads the operation's own contract to work out how the "
            "endpoint pages. Only override if a fetch came back incomplete because no "
            "strategy was recognised, and the operation's parameters show which applies."
        ),
    )
    refresh: bool = Field(
        default=False,
        description=(
            "Re-fetch from GHL even if today's cached copy exists. Use it when the user "
            "has just changed something in the CRM and expects to see it, or when they "
            "ask for fresh numbers."
        ),
    )
