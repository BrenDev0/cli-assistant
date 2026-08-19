# CLI Assistant

A terminal-based AI assistant built from scratch in Python, exploring agent
architecture, tool-calling, and self-extending behavior without relying on a
pre-built agent framework.

## Overview

CLI Assistant runs a conversational agent loop directly in the terminal. It
maintains conversation state across turns, exposes a set of tools the model
can call (file system operations, skill management), and executes those tool
calls through an async runtime. Its most distinctive feature is a
**skill-builder sub-assistant**: the main agent can delegate to a second,
narrower-scoped agent that authors new "skills" — self-contained instruction
folders — which the main assistant then discovers and follows on future
turns. This gives the assistant a simple form of persistent, self-directed
capability growth.

## Architecture

- **Agent core** (`src/core/agents`) — a small `Agent` protocol plus a
  concrete `LangchainAgent` implementation that wraps LangChain chat models,
  runs the tool-calling loop (model → tool calls → tool results → model,
  up to a bounded number of iterations), and executes tool calls concurrently
  with `asyncio.gather`.
- **Tools layer** (`src/tools`) — a registry mapping Pydantic schemas to
  Python functions, with a generic `executor` that dispatches by tool name
  and transparently supports both sync and async tool implementations. Tools
  are sandboxed to the project root to prevent path traversal.
- **Assistants** (`src/assistants`) — two configured "personas" built on the
  same agent core:
  - **Orchestrator**: the main, user-facing assistant with full tool access.
  - **Skill Builder**: a restricted sub-assistant (file tools only) invoked
    by the orchestrator's `build_skill` tool. It writes/updates
    `SKILL.md` files under `.my_assistant/skills/<name>/`, which the
    orchestrator lists and reads back on subsequent turns.
- **CLI entry point** (`src/main.py`) — a Click-based chat loop that refreshes
  the available-skills listing every turn and streams responses to the
  terminal.

## Key design choices

- **Framework-light by intent** — LangChain is used only as a thin, swappable
  wrapper around chat model providers; the agentic loop, tool dispatch, and
  multi-agent delegation are hand-rolled rather than adopted from a heavier
  agent framework.
- **Provider-agnostic model layer** — the same `LangchainAgent` class drives
  either OpenAI or Anthropic models by name, making it straightforward to
  add or switch providers.
- **Self-extending skills** — skills are plain instruction files an agent
  writes and another agent later reads, rather than code — a lightweight
  take on giving an LLM assistant durable, inspectable memory of "how to do
  things."
- **Safety-conscious tool design** — all file tools resolve paths against a
  fixed project root and reject any path that would escape it.

## Frameworks & tools

- **Python 3.12+**
- **LangChain** (`langchain-openai`, `langchain-anthropic`) — chat model
  abstraction
- **Pydantic / Pydantic Settings** — tool schemas and environment-based
  configuration
- **Click** — CLI interface
- **uv** — dependency management and packaging (`pyproject.toml` + `uv.lock`)
- **Hatchling** — build backend

## Status

Personal/experimental project used to prototype agent-loop and tool-calling
patterns rather than a production system.
