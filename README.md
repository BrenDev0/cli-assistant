# CLI Assistant

A terminal-based AI assistant built from scratch in Python, exploring agent
architecture, tool-calling, background execution, and self-extending behavior
without relying on a pre-built agent framework.

## Overview

CLI Assistant runs a conversational agent loop directly in the terminal. It
maintains conversation state across turns, exposes 19 tools the model can call
(file system, GoHighLevel CRM, web search, background tasks, conversation
history), and executes those calls through an async runtime.

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
- **CLI** (`src/cli`) — prompt_toolkit chat loop, command dispatcher, styled
  output, and the status bar showing live background-task activity.

## Tools

| group | tools |
|---|---|
| files | read, list, search, create file/dir, update, delete file/dir |
| GoHighLevel | describe and execute any of 36 CRM operations over MCP |
| web | search, extract, map, crawl (Tavily) |
| background | start task, check task |
| skills | build, list |
| history | search past conversations |

## Key design choices

- **Framework-light by intent** — LangChain wraps chat model providers only;
  the agent loop, tool dispatch, and multi-agent delegation are hand-rolled.
- **Provider-agnostic models** — the API key is derived from the model name, so
  switching models can never send the wrong provider's credentials. 14 models
  across OpenAI and Anthropic, switchable at runtime with `/model`.
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
- **Self-extending skills** — skills are plain instruction files one agent
  writes and another later reads, rather than code.

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
