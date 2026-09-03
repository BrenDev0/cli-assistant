# CLI Assistant

A terminal-based AI assistant built from scratch in Python, exploring agent
architecture, tool-calling, background execution, and self-extending behavior
without relying on a pre-built agent framework.

## Overview

CLI Assistant runs a conversational agent loop directly in the terminal. It
maintains conversation state across turns, exposes 23 tools the model can call
(file system, GoHighLevel CRM, web search, HTML authoring, background tasks,
conversation history), and executes those calls through an async runtime.

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
uv tool install -e .        # `my_assistant` on PATH, tracks your edits
uv tool update-shell        # once, if the command isn't found
```

Then run `my_assistant` from any directory.

## Where things live

Two roots, deliberately separated:

```
~/.my_assistant/          global workspace — follows you between projects
    skills/               built once, available everywhere
    history/              every conversation, searchable across projects
    tasks/                background task output and records

<launch directory>/       the active project — your own files
```

A path beginning `.my_assistant/` always resolves to the global workspace, from
any directory. Everything else is project-relative. File tools are sandboxed to
those two roots and reject anything that would escape either.

The launch directory is the project for now; explicit project selection is the
next step.

`.env` keys — only `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` is required:

```
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...      # optional, needed for claude-* models
TAVILY_API_KEY=...         # optional, needed for the web tools
GHL_PIT=...                # optional, GoHighLevel private integration token
GHL_LOCATION_ID=...
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
    to `~/.my_assistant/tasks/<slug>-<id>/`.
  - **Skill Builder** — file tools only, authors `SKILL.md` under
    `~/.my_assistant/skills/<name>/`.
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
| GoHighLevel | describe and execute any of 36 CRM operations over MCP |
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
  `~/.my_assistant/` so they follow the user, while deliverables stay in the
  project. Skills built in one directory used to be invisible in every other.
- **A task's workspace is not its delivery address** — a worker still does all
  its work in `~/.my_assistant/tasks/<slug>/`, which keeps drafts out of the
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
- **Design is a decision, not a decoration pass** — "make it styled" constrains
  nothing, so a model styles a page one tag at a time and every implicit choice
  falls back to the median of its training data: Arial, black on white, a
  stacked column of full-width text. The HTML builder blocks that from two
  sides. A house design system in `src/assistants/html_builder/design.py` states
  exact tokens and names the defaults it bans, and an art-direction pass has to
  commit to typefaces, hex values and a layout in writing before any markup
  exists. Styling stays inside that assistant rather than becoming a design
  agent it calls: design and markup are one artifact, and a separate agent would
  be writing CSS for a DOM it cannot see. `.my_assistant/design/brand.md`
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
