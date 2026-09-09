import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from src.core.settings import settings
from src.core.workspace import data_dir
from src.tools.files.tools import _shown
from src.tools.ghl.tools import describe_operation, execute_ghl_operation

from . import paging as pg
from .paging import GhlFetchError
from .profile import profile, table

ROWS_FILE = "rows.ndjson"
MANIFEST_FILE = "manifest.json"

# A hard stop on the loop itself, independent of max_rows. A strategy whose cursor works
# but never advances would otherwise page forever against the user's live API.
MAX_PAGES = 600

# GHL's documented burst allowance is 100 requests per 10 seconds per location. At 100
# rows a page that is 10,000 rows of headroom per 10 seconds, so pacing costs nothing
# real and keeps a large fetch from tripping a 429 halfway through.
PAGE_PAUSE = 0.15

INCOMPLETE = "INCOMPLETE"


def _slug(text: str, limit: int = 40) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned[:limit].rstrip("-") or "dataset"


def _today() -> str:
    """The date stamp every dataset folder carries. Local time, matching the user's sense
    of "today" rather than UTC's -- the manifest records an exact UTC fetched_at anyway."""
    return datetime.now().strftime("%Y%m%d")


async def fetch_ghl_dataset(
    name: str,
    operation_id: str,
    params: dict | None = None,
    max_rows: int = 5000,
    fields: list[str] | None = None,
    pagination: str = "auto",
    refresh: bool = False,
) -> str:
    """Page a GHL read operation to disk and return a description of what landed.

    The return value is a manifest -- row count, field profile, path -- and never rows.
    That is the whole point of the tool: the rows exist on disk where something can count
    them exactly, instead of in a context window where they have to be counted by
    impression.
    """
    folder = data_dir() / f"{_slug(name)}-{_today()}"
    manifest_path = folder / MANIFEST_FILE
    request = {"operation_id": operation_id, "params": params or {}, "fields": fields}

    cached = _cached(folder, request, refresh)
    if cached:
        return cached

    try:
        operation = pg.contract_of(await describe_operation(operation_id))
    except GhlFetchError as exc:
        return f"Could not fetch '{name}': {exc}"

    # Read-only by construction, checked against the server's own classification rather
    # than the operation's name. This tool loops without approval and runs unsupervised
    # inside background tasks, so it must not be reachable as a bulk write path -- and
    # "fetch" in a tool name has never stopped a model from passing it a delete.
    kind = operation.get("kind")
    if kind != "read":
        return (
            f"Refusing to fetch with '{operation_id}': the GHL server classifies it as "
            f"'{kind}', not a read. This tool only ever reads. Use ExecuteGhlOperation "
            f"for anything that writes, and search again with kind='read' if you were "
            f"looking for the list version of this operation."
        )

    if pagination != "auto":
        strategy = pg.STRATEGIES.get(pagination)
        if strategy is None:
            return (
                f"Unknown pagination '{pagination}'. Valid values: auto, "
                f"{', '.join(pg.STRATEGIES)}."
            )
    else:
        strategy = pg.detect(operation)

    try:
        result = await _fetch(
            operation=operation,
            operation_id=operation_id,
            params=params or {},
            strategy=strategy,
            max_rows=max_rows,
            fields=fields,
            folder=folder,
        )
    except GhlFetchError as exc:
        return f"{INCOMPLETE} -- fetching '{name}' failed: {exc}"

    manifest = {
        "name": name,
        "operation_id": operation_id,
        "params": params or {},
        "fields": fields,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pagination": strategy.describe() if strategy else "none",
        "rows_file": _shown(folder / ROWS_FILE),
        **result,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    return _report(manifest)


async def _fetch(
    operation: dict,
    operation_id: str,
    params: dict,
    strategy: pg.Paging | None,
    max_rows: int,
    fields: list[str] | None,
    folder: Path,
) -> dict:
    """The page loop. Writes rows as they arrive, so an interruption leaves the pages that
    did land rather than nothing, and returns everything the manifest needs to state
    plainly whether the dataset is whole."""
    base = pg.normalize(params, bool(operation.get("hasRequestBody")))
    _inject_location(base, operation)

    size_slot = pg.size_param_for(operation, strategy) if strategy else None
    folder.mkdir(parents=True, exist_ok=True)
    rows_path = folder / ROWS_FILE

    # Every row that lands in the file, kept to be profiled. Bounded by max_rows, and
    # exact by construction: the counts in the manifest are counted, not sampled.
    written: list[dict] = []

    cursor: dict | None = None
    seen_cursors: set[str] = set()
    pages = 0
    reported_total: int | None = None
    row_key: str | None = None
    # The page size to measure a short final page against. Known up front only when the
    # operation takes a size parameter; otherwise it is whatever the server's own default
    # turns out to be, learned from page one. Guessing it instead -- assuming 100 when
    # GHL defaults to 20 -- makes the first page look short and ends the fetch at 20 rows
    # while reporting it as the complete set.
    expected: int | None = None
    stopped = ""

    with rows_path.open("w", encoding="utf-8", newline="\n") as sink:
        while True:
            request = {group: dict(values) for group, values in base.items()}
            asked = min(pg.MAX_PAGE_SIZE, max_rows - len(written))

            if size_slot:
                slot, group = size_slot
                pg.place(request, group, slot, asked)
                expected = asked

            if cursor and strategy:
                for key, value in cursor.items():
                    pg.place(request, strategy.cursor_in, key, value)

            if strategy and strategy.page_param:
                pg.place(request, "query", strategy.page_param, pages + 1)

            data = pg.payload(await execute_ghl_operation(operation_id, request))
            pages += 1

            rows, row_key = pg.rows_from(data, prefer=row_key)
            reported_total = pg.total_from(data) or reported_total

            if not rows:
                stopped = "a page came back empty, so there was no more data"
                break

            for row in rows[: max_rows - len(written)]:
                kept = _project(row, fields)
                sink.write(json.dumps(kept, default=str) + "\n")
                written.append(kept)

            if expected is None:
                expected = len(rows)

            if len(written) >= max_rows:
                stopped = f"max_rows ({max_rows}) was reached"
                break

            if reported_total is not None and len(written) >= reported_total:
                stopped = "every row GHL reported had been written"
                break

            if strategy is None:
                stopped = (
                    "this operation exposes no pagination parameter the fetcher "
                    "recognises, so only the first page was retrieved"
                )
                break

            if len(rows) < expected:
                stopped = "the last page was short, so there was no more data"
                break

            if pages >= MAX_PAGES:
                stopped = f"the page limit ({MAX_PAGES}) was reached"
                break

            if not strategy.page_param:
                cursor = pg.cursor_from(rows[-1], strategy)
                if cursor is None:
                    carried = ", ".join(
                        " or ".join(fields) for fields, _ in strategy.cursor_map
                    )
                    stopped = (
                        f"the last row carried no cursor -- '{strategy.kind}' paging "
                        f"reads it from row field(s) '{carried}', which this operation's "
                        f"rows do not contain, so paging stopped after {pages} page(s)"
                    )
                    break

                fingerprint = json.dumps(cursor, sort_keys=True, default=str)
                if fingerprint in seen_cursors:
                    stopped = "the cursor stopped advancing, so paging was halted"
                    break
                seen_cursors.add(fingerprint)

            await asyncio.sleep(PAGE_PAUSE)

    fields_profile = profile(written)

    return {
        "rows": len(written),
        "reported_total": reported_total,
        "pages": pages,
        "complete": _complete(len(written), reported_total, max_rows, strategy),
        "stopped_because": stopped,
        "row_key": row_key,
        "bytes": rows_path.stat().st_size,
        "field_count": len(fields_profile),
        "profile": fields_profile,
    }


def _complete(rows: int, total: int | None, max_rows: int, strategy) -> bool:
    """Whether the file holds the whole result set.

    GHL reports a `total` on its search endpoints, which makes this checkable rather than
    a matter of trust: the fetch is whole when it wrote as many rows as the API said
    existed. With no total to compare against there is nothing to check, so a fetch that
    stopped on its own row cap, or ran with no paging strategy at all, is called partial.
    Assuming the opposite is how a 20-row first page gets reported as a full quarter.
    """
    if total is not None:
        return rows >= total

    return strategy is not None and rows < max_rows


def _inject_location(params: dict, operation: dict) -> None:
    """Supply locationId where the operation declares one and the caller did not.

    The bound location is injected server-side for most operations, which is why the
    contacts search works without it -- but several declare it as a required parameter
    and answer 401 without it, which reads exactly like a missing scope. The value is
    already in settings, so requiring the model to remember it buys nothing but a class
    of confusing failure.
    """
    if not settings.GHL_LOCATION_ID:
        return

    if any("locationId" in params.get(group, {}) for group in pg.GROUPS):
        return

    for parameter in operation.get("parameters", []):
        if isinstance(parameter, dict) and parameter.get("name") == "locationId":
            group = parameter.get("in") if parameter.get("in") in pg.GROUPS else "query"
            pg.place(params, group, "locationId", settings.GHL_LOCATION_ID)
            return

    if "locationId" in (operation.get("parameterNames") or []):
        pg.place(params, "query", "locationId", settings.GHL_LOCATION_ID)


def _project(row: dict, fields: list[str] | None) -> dict:
    """Top-level fields only -- a deliberate floor, not an oversight. Flattening nested
    objects here would invent column names that appear in no GHL response, and the query
    layer can reach into nested JSON without help."""
    if not fields:
        return row
    return {key: row.get(key) for key in fields}


def _cached(folder: Path, request: dict, refresh: bool) -> str | None:
    """Today's dataset for this exact request, under any name.

    Matched on the request (operation, params, fields) rather than on the dataset name,
    because the name is the caller's label and the request is what determines the rows.
    Keying on the name meant a re-ask under any new label missed and re-pulled identical
    data: one session produced eight duplicate "-refreshed" folders that way, ~6,600
    tokens of manifests for rows already on disk. A different request under a name already
    in use still re-fetches -- two questions must never serve each other's rows.
    """
    if refresh:
        return None

    for candidate in sorted(data_dir().glob(f"*-{_today()}/{MANIFEST_FILE}")):
        try:
            manifest = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if not all(manifest.get(key) == value for key, value in request.items()):
            continue
        if not (candidate.parent / ROWS_FILE).is_file():
            continue

        note = (
            f"Fetched {manifest['fetched_at']} and read from disk just now -- no API "
            f"calls were made. This IS the current data for that request; do not re-fetch "
            f"it under another name to get something fresher, which only writes a second "
            f"copy of the same rows. If the CRM has genuinely changed since and you need "
            f"it re-pulled, call this again with the SAME name and refresh=True."
        )
        if candidate.parent != folder:
            note += (
                f"\nIt was fetched under the name '{manifest['name']}', so the rows are at "
                f"the path above rather than under the name you passed."
            )

        return f"{_report(manifest)}\n\n{note}"

    return None


def _report(manifest: dict) -> str:
    total = manifest.get("reported_total")
    rows = manifest["rows"]

    headline = f"{rows:,} rows"
    if total is not None:
        headline += f" of {total:,} reported by GHL"

    lines = [
        f"Dataset '{manifest['name']}': {headline}, "
        f"{manifest['field_count']} fields, {manifest['bytes']:,} bytes.",
        f"Rows:     {manifest['rows_file']}  (one JSON object per line)",
        f"Manifest: {_manifest_path(manifest)}",
        f"As of:    {manifest['fetched_at']}  via {manifest['operation_id']}",
        f"Paging:   {manifest['pagination']} over {manifest['pages']} page(s)",
    ]

    if manifest["complete"]:
        lines.append("Complete: yes -- every row GHL reported was written.")
    else:
        lines.append(
            f"Complete: NO. Paging stopped because {manifest['stopped_because']}. "
            f"Any figure from this file describes {rows:,} rows, not the whole set -- "
            f"say so in anything you report, and never present it as the full picture."
        )

    lines += ["", "Fields:", table(manifest.get("profile") or [])]

    if manifest.get("fields"):
        lines.append(
            f"\nOnly these fields were kept: {', '.join(manifest['fields'])}. "
            f"Anything else GHL returned is not in the file."
        )

    return "\n".join(lines)


def _manifest_path(manifest: dict) -> str:
    rows_file = manifest["rows_file"]
    return rows_file[: -len(ROWS_FILE)] + MANIFEST_FILE
