# CLI Assistant

A terminal-based AI assistant built from scratch in Python, exploring agent
architecture, tool-calling, background execution, and self-extending behavior
without relying on a pre-built agent framework.

## Overview

CLI Assistant runs a conversational agent loop directly in the terminal. It
maintains conversation state across turns, exposes 25 tools the model can call
(file system, GoHighLevel CRM, dataset fetching, web search, HTML authoring,
background tasks, conversation history), and executes those calls through an async
runtime.

Two features shape most of the design:

- **Background tasks** — long work (research, authoring, multi-step jobs) is
  delegated to a sub-agent that runs concurrently while the conversation
  continues. Results are announced the moment they land, without the user
  having to ask.
- **Self-extending skills** — the assistant can author "skills", self-contained
  instruction folders it discovers and follows on later turns, giving it a
  simple form of durable, inspectable capability growth.

## Install

```bash
git clone <this repo> && cd cli-assistant
uv sync                     # create .venv and install dependencies
uv tool install -e .        # `the-way` on PATH, tracks your edits
uv tool update-shell        # once, if the command isn't found
```

Create a `.env` **in the cloned repo directory** with at least one model key:

```
OPENAI_API_KEY=...
```

The `.env` is always read from the clone (`settings.py` resolves it from the
package location), never from the directory you launch in. That matters because
`the-way` is meant to be run from whatever project you are working on — the
launch directory is the project, but the configuration stays with the code.

Then run `the-way` from any directory. Everything except the model key is
optional: missing integrations print one line at startup and disable their own
tools, so a first run works with nothing but `OPENAI_API_KEY`.

### Connecting GoHighLevel

The CRM tools need a private integration token and the sub-account id:

```
GHL_PIT=pit-...             # GoHighLevel private integration token
GHL_LOCATION_ID=...         # the sub-account (location) to work in
```

In GoHighLevel, the token comes from the sub-account's **Settings → Private
Integrations → Create new integration**; it is shown once, so copy it then. The
location id is in **Settings → Business Profile**, and also sits in the URL of
any sub-account page (`/location/<GHL_LOCATION_ID>/...`).

Grant the read scopes for the data you intend to analyse — the token's scopes are
the real limit on what the assistant can see, and a missing one surfaces as a
`401` naming the operation it refused:

```
contacts.readonly  conversations.readonly  opportunities.readonly
calendars.readonly  users.readonly  locations/customFields.readonly
```

`opportunities.readonly` is the one worth checking. Most CRM analysis — pipeline
value, conversion rates, velocity by stage — is unanswerable without it, and its
absence is invisible until something asks for it.

### First run

```
$ the-way

  the way
  ──────────────────────────────────────────────
  25 tools · 4 GHL · gpt-5.1
  /help for commands · 'exit' to leave

> how many contacts do I have, and how many have an email address?
```

Ask questions about the CRM in plain language. Anything touching GoHighLevel is
delegated to a background task, so the answer arrives a little later and the
prompt stays usable meanwhile — you will be asked which folder finished files
should land in. Counting questions pull the whole result set to
`~/.the_way/data/` first; the reply states the row count it is based on, and
says so explicitly when a fetch came back partial.

## Where things live

Two roots, deliberately separated:

```
~/.the_way/          global workspace — follows you between projects
    skills/               built once, available everywhere
    history/              every conversation, searchable across projects
    tasks/                background task output and records
    data/                 fetched CRM datasets, one folder per pull

<launch directory>/       the active project — your own files
```

A path beginning `.the_way/` always resolves to the global workspace, from
any directory. Everything else is project-relative. File tools are sandboxed to
those two roots and reject anything that would escape either.

The launch directory is the project for now; explicit project selection is the
next step.

Full `.env` reference — only one model key is required, and every other line
disables a group of tools by its absence rather than breaking the app:

```
OPENAI_API_KEY=...         # required unless ANTHROPIC_API_KEY is set
ANTHROPIC_API_KEY=...      # optional, needed for claude-* models
TAVILY_API_KEY=...         # optional, needed for the web tools
GHL_PIT=...                # optional, GoHighLevel private integration token
GHL_LOCATION_ID=...        # optional, required alongside GHL_PIT
```

## Commands

| | |
|---|---|
| `/tokens` | context breakdown — tool schemas, static prefix, history |
| `/compress` | summarise the conversation and drop the transcript |
| `/clear` | drop the conversation entirely |
| `/model [name]` | show or switch the model mid-conversation |
| `/help` | list commands |
| `exit` | leave |

## Architecture

- **Agent core** (`src/core/agents`) — an `Agent` protocol plus `LangchainAgent`,
  which wraps LangChain chat models and runs the tool-calling loop (model →
  tool calls → tool results → model) up to a configurable iteration cap,
  executing tool calls concurrently with `asyncio.gather`.
- **Workspace** (`src/core/workspace.py`) — resolves the two roots. The project
  root is a runtime lookup rather than an import-time constant, so it can be
  scoped per session later instead of per process.
- **Frontend protocol** (`src/core/frontend.py`) — the core reports progress and
  requests approval through a protocol, never by printing. `CliFrontend`
  implements it for the terminal; a web frontend would implement the same six
  methods. Nothing in `src/core` or `src/tools` imports a UI library.
- **Tools layer** (`src/tools`) — a registry mapping Pydantic schemas to Python
  functions, with a generic `executor` that dispatches by tool name, supports
  sync and async implementations, emits tool events, and gates write operations
  behind approval. Tools are sandboxed to the project and workspace roots.
- **Assistants** (`src/assistants`) — configured personas on the same core:
  - **Orchestrator** — user-facing, full tool access.
  - **Background Task** — spawned per task, gets every tool except the
    background ones so workers cannot spawn workers, and a higher iteration
    cap (30) because research burns steps before it writes anything. Output goes
    to `~/.the_way/tasks/<slug>-<id>/`.
  - **Skill Builder** — file tools only, authors `SKILL.md` under
    `~/.the_way/skills/<name>/`.
  - **HTML Builder** — authors one self-contained, designed HTML page. Runs two
    passes over the same assistant: an art-direction pass with no write tools
    that commits to typefaces, hex values and layout in a written brief, then a
    build pass that executes it and revises itself once.
- **CLI** (`src/cli`) — prompt_toolkit chat loop, command dispatcher, styled
  output, and the status bar showing live background-task activity.

## Tools

| group | tools |
|---|---|
| files | read, list, search, create file/dir, update, copy, move, delete file/dir |
| GoHighLevel | search, describe and execute any CRM operation over MCP |
| data | fetch a paged CRM read to disk and profile it |
| web | search, extract, map, crawl (Tavily) |
| html | build page (report, landing, dashboard, article) |
| background | start task, check task, deliver task output |
| skills | build, list |
| history | search past conversations |

## Key design choices

- **Framework-light by intent** — LangChain wraps chat model providers only;
  the agent loop, tool dispatch, and multi-agent delegation are hand-rolled.
- **Provider-agnostic models** — the API key is derived from the model name, so
  switching models can never send the wrong provider's credentials. 28 models
  across OpenAI and Anthropic, switchable at runtime with `/model`. Only models
  that support tool calling are listed: a model that cannot call tools can do
  nothing in a tool-calling loop, so offering it in the menu is a trap.
- **Temperature support is an allowlist, not a blocklist** — reasoning tiers
  reject the parameter outright and return a 400, while a model that accepts one
  and is not given one simply uses its default. The failure is asymmetric, so
  only models verified to take a temperature are sent one, and anything added
  later is safe by default rather than broken by default.
- **Model strength is assigned per assistant, by supervision and blast radius** —
  the background worker gets the strongest, because it is the only agent that
  runs with nobody at the keyboard (approval is skipped when `CURRENT_TASK` is
  set), runs the deepest loop, and writes the file the client opens. The
  orchestrator sits a tier below: its mistakes surface in the next line of chat.
  The skill builder is cheapest — writing a `SKILL.md` to a spelled-out layout is
  not a reasoning problem.
- **Reports are verified, not trusted** — a background worker's claim that it
  wrote a file is checked against the filesystem before being relayed, and the
  orchestrator is told to relay results rather than embellish them. A model
  handed a gap will fill it convincingly; the fix is to remove the gap.
- **Context is budgeted deliberately** — the system prompt and CRM catalog form
  a cacheable static prefix, volatile per-turn context sits behind it, and
  history is trimmed to the last 10 turns at user-message boundaries so a tool
  result is never orphaned from its call. Trimmed turns stay searchable on disk.
- **Human in the loop on writes** — file creation, updates, and deletion prompt
  for approval with three outcomes: yes, no, or redirect with an instruction the
  model must follow instead.
- **Global workspace, local projects** — skills and history live in
  `~/.the_way/` so they follow the user, while deliverables stay in the
  project. Skills built in one directory used to be invisible in every other.
- **A task's workspace is not its delivery address** — a worker still does all
  its work in `~/.the_way/tasks/<slug>/`, which keeps drafts out of the
  project, but that folder is unreachable for anyone who does not already know
  it exists. So `StartBackgroundTask` takes a `deliver_to` folder, asked of the
  user before the task starts, and the runtime copies the finished files there
  on success — copies, so the task folder survives as the record of what was
  produced. `DeliverTask` does the same after the fact, by task id.
- **Bytes move on disk, never through the model** — `copy_path`, `move_path`
  and `deliver_task` exist so that "put this file over there" is a filesystem
  operation. Without them the only way to move a file is to read it and
  re-create it, which round-trips the contents through a context window that can
  truncate them, summarise them, or substitute something that was never read.
  A directory listing is not file content, and a model with no move tool will
  eventually write one as if it were.
- **Self-extending skills** — skills are plain instruction files one agent
  writes and another later reads, rather than code.
- **Numbers are counted, not read** — `ExecuteGhlOperation` returns one page, so
  answering "how many contacts converted last month" from it is wrong twice
  over: it describes 20 of several thousand records, and the arithmetic happens
  by impression inside a context window. `FetchGhlDataset` pages the whole
  result set to `.the_way/data/<name>-<date>/rows.ndjson` and returns a
  *manifest* — row count against the total GHL itself reported, per-field null
  rates and value ranges, and the path. The rows never enter anyone's context,
  which is the same argument as `copy_path`: data a model retypes is data it can
  quietly alter. The profile deliberately stops at shape and computes no
  summary statistics, because a sum produced here would arrive with nothing to
  check it against.
- **A partial fetch says so** — GHL reports a `total` on its search endpoints,
  so completeness is checkable rather than assumed: the manifest states
  `Complete: NO` with the reason whenever the row count falls short, and with no
  total to compare against a fetch is called partial rather than whole. Silent
  truncation is the failure that matters here, because 600 rows reported as a
  full quarter looks exactly like the real thing.
- **Pagination is per-operation, and it lives in one file** — GHL does not
  paginate one way. `search-contacts-advanced` takes `pageLimit` in a POST body
  and expects the *last row's own* `searchAfter` array echoed back;
  `search-conversation` takes `limit` in the query string and a `startAfterDate`
  cursor the rows carry under `sort`; others offer only a page number. So the
  cursor is a property of the rows, not of the response envelope. Each shape is
  a `Paging` record in `src/tools/data/paging.py` detected from the operation's
  own contract, and an unrecognised shape returns `None` rather than a guess — a
  wrong parameter name is silently ignored by GHL and comes back looking like a
  complete one-page dataset.
- **The fetcher is read-only by construction** — it checks the server's own
  `kind` classification and refuses anything that is not a read. It loops without
  approval and runs unsupervised inside background tasks, so it must not be
  reachable as a bulk write path, and "fetch" in a tool name has never stopped a
  model from passing it a delete.
- **Design is a decision, not a decoration pass** — "make it styled" constrains
  nothing, so a model styles a page one tag at a time and every implicit choice
  falls back to the median of its training data: Arial, black on white, a
  stacked column of full-width text. The HTML builder blocks that from two
  sides. A house design system in `src/assistants/html_builder/design.py` states
  exact tokens and names the defaults it bans, and an art-direction pass has to
  commit to typefaces, hex values and a layout in writing before any markup
  exists. Styling stays inside that assistant rather than becoming a design
  agent it calls: design and markup are one artifact, and a separate agent would
  be writing CSS for a DOM it cannot see. `.the_way/design/brand.md`
  overrides the house system per user.

## Frameworks & tools

- **Python 3.12+**
- **LangChain** (`langchain-openai`, `langchain-anthropic`) — chat model
  abstraction
- **prompt_toolkit** — async prompt, status bar, output that survives
  concurrent writes from background tasks
- **Pydantic / Pydantic Settings** — tool schemas and environment configuration
- **Tavily** — web search and extraction
- **MCP** (hand-rolled streamable-HTTP client) — GoHighLevel integration
- **Click** — CLI entry point and terminal styling
- **uv** — dependency management and packaging
- **Hatchling** — build backend

## Status

Personal/experimental project used to prototype agent-loop, tool-calling, and
background-execution patterns rather than a production system.
