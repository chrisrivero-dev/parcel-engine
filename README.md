# Forge --- Local Code Assistant

### (Evolving into Overseer --- Deterministic Engineering Supervisor)

Forge is a production-grade local coding assistant that connects to any
OpenAI-compatible LLM endpoint (LM Studio, Ollama, vLLM, etc.),
generates validated unified diffs, and allows preview, application, or
rejection of changes through a two-panel interface.

Forge provides the **interactive execution surface**.

Overseer is the next layer: a **deterministic supervisory backbone**
that adds persistence, telemetry, and orchestration.

------------------------------------------------------------------------

# 🚧 Overseer Roadmap (Active Development)

Forge currently handles:

-   Diff generation
-   Validation
-   Git safety enforcement
-   Human-in-the-loop approval

Overseer adds:

-   Persistent SQLite state store
-   Job queue
-   Worker daemon
-   Project registry
-   Deterministic project health telemetry

**Current milestone:**\
Phase 1 --- Deterministic Backbone\
(SQLite + job queue + worker + telemetry)\
No autonomy expansion.\
No architectural redesign.\
Deterministic before intelligent.

------------------------------------------------------------------------

# Quick Start

``` bash
# 1. Clone and setup
cd local-code-assistant
chmod +x setup.sh run.sh
./setup.sh

# 2. Start LM Studio and load a model (e.g., Qwen 14B)

# 3. Run Forge pointed at your repo
REPO_PATH=/path/to/your/project ./run.sh

# 4. Open http://localhost:5173
```

------------------------------------------------------------------------

# Architecture Overview

Execution Layer (Forge): - React + Vite frontend - FastAPI backend -
AgentService → DiffService → GitService pipeline - SSE streaming -
Scoped file injection - Unified diff validation

Backbone Layer (Phase 1): - SQLite state_store - Job queue - Worker
daemon - Project registry - Telemetry engine

LLM Layer: - LM Studio / Ollama / vLLM / OpenAI-compatible endpoint

------------------------------------------------------------------------

# Core Features

-   Two-panel layout: chat left, diff preview right
-   Streaming token display via SSE
-   Unified diff generation with syntax highlighting
-   Apply / Reject / Retry controls
-   Keyboard shortcuts: ⌘⏎ Apply, ⌘⌫ Reject, ⌘R Retry

------------------------------------------------------------------------

# Safety Guarantees

-   git apply --check before patch application
-   Scoped file validation
-   Diff format validation
-   Markdown fence stripping
-   Path traversal protection
-   No silent merges
-   Hard retry caps
-   Auto-commit requires explicit configuration

------------------------------------------------------------------------

# Phase Structure

  Layer                 Responsibility
  --------------------- -------------------------------------------
  Execution             Diff generation + validation + git safety
  Backbone (Phase 1)    Persistence + queue + telemetry
  Escalation (Future)   Structured repair via LLM
  Integration           UI surface + job visibility

------------------------------------------------------------------------

# Design Principles

-   Deterministic \> Generative
-   Git is the transaction boundary
-   No silent file mutations
-   No auto-merge
-   Persistence before intelligence
-   LLMs are escalation tools, not default tools

------------------------------------------------------------------------

# Current Status

Forge: - Stable execution engine - Safe diff validation pipeline -
Human-controlled workflow

Overseer Phase 1: - Deterministic backbone in progress - No autonomy
features yet - Infrastructure-first build

------------------------------------------------------------------------

# Future Direction (Post-Backbone)

-   Self-healing validation loop
-   Structured repair service
-   Health scoring
-   Cross-repo telemetry
-   Predictive maintenance

Autonomy will only be added after deterministic infrastructure is proven
stable.

------------------------------------------------------------------------

Last updated: 2026-02-26 16:43:16 UTC
