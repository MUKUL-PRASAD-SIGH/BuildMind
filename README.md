# 🧠 BuildMind

> **AI Thinking Infrastructure** — the operating system for human-AI collaborative engineering, running directly in your IDE terminal.

```
Human     = Strategy  (you make decisions, in your terminal)
AI        = Execution (models already in your IDE — no API keys)
BuildMind = Orchestrator (runs the pipeline, enforces rules)
```

---

## 🖥️ How You Use It (IDE-Native, Zero Setup)

BuildMind is a **Python CLI tool + MCP server** that runs in your IDE's terminal and uses the models already available in your IDE (Antigravity has Claude Haiku, Sonnet, Opus, Gemini Pro, and more — no API keys needed).

```bash
# Install
pip install buildmind

# Run inside any project
buildmind start "Build a task management API with authentication"
```

**Works for any project type:**
```bash
buildmind start "Build a REST API with authentication"
buildmind start "Build a React dashboard with charts"
buildmind start "Build a CLI tool for file compression"
buildmind start "Build a Stripe payment integration"
buildmind start "Build a real-time chat system"
buildmind start "Build a web scraper with rate limiting"
buildmind start "Build a microservice for email sending"
```

---

## 🤖 Uses Your IDE's Models — No API Keys

BuildMind connects to your IDE's AI (Antigravity) via MCP. Your IDE already has access to:

| Model | Used For |
|-------|---------|
| `claude-opus` | Task decomposition (deep reasoning) |
| `claude-sonnet` | Code generation, decision cards, explanations |
| `claude-haiku` | Classification, validation (fast + cheap) |
| `gemini-pro` | Fallback / alternative reasoning |
| `gemini-flash` | Fast classification fallback |

**No `.env` file. No API key configuration. Your IDE handles all of that.**

---

## 🧩 Human Decisions — All In Terminal, All Options Listed

When BuildMind needs your input, it surfaces **every realistic option with honest tradeoffs** — all inline in your terminal, no browser needed:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🧩 DECISION: Choose Authentication Strategy
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  WHY YOU: Auth strategy shapes your entire security model.
           This is hard to change later without major refactoring.

  [1]  JWT (stateless)        — APIs, mobile, SPAs
  [2]  Session-based          — web apps, admin tools  ← AI recommends
  [3]  OAuth / OpenID         — social login, SSO
  [4]  API Keys               — machine-to-machine APIs
  [5]  Custom — describe your approach

  > explain 1        ← type to get a deep dive on any option
  > compare 1 2      ← side-by-side comparison

  Enter choice [1-5] or command:
  >
```

All explanations generated inline by your IDE's AI. No ChatGPT. No browser tabs.

---

## ⚙️ AI Tasks — Written Directly to Your Project

```
your-project/
├── src/
│   └── auth/
│       ├── jwt_service.py      ← Written by AI (used your decision: JWT)
│       └── routes.py           ← Written by AI
├── .buildmind/
│   ├── decisions.json          ← Every choice you made
│   └── audit_log.jsonl         ← Complete history
└── BUILDMIND_SUMMARY.md        ← What was built + why
```

---

## 📚 Documentation

| Doc | Description |
|-----|-------------|
| [**IDE Integration** ⭐ START HERE](./docs/15-ide-integration.md) | Setup, full terminal demo, CLI commands |
| [Vision & Positioning](./docs/01-vision-and-positioning.md) | Product philosophy + differentiation |
| [System Architecture](./docs/02-system-architecture.md) | Full system design — generic, any project type |
| [Task Decomposer](./docs/03-task-decomposer.md) | How any project gets broken into atomic tasks |
| [Decision Engine](./docs/04-decision-engine.md) | Terminal decision cards — options, `explain <num>` |
| [Compulsion Layer](./docs/05-compulsion-layer.md) | Anti-autonomy enforcement |
| [Router & Model Strategy](./docs/06-router-and-model-strategy.md) | IDE models (Haiku/Sonnet/Opus/Gemini) — no keys |
| [Graph Engine](./docs/07-graph-engine.md) | ASCII terminal graph + JSON for visualization |
| [Explanation Engine](./docs/08-explanation-engine.md) | Code → plain English, inline in terminal |
| [Database Schema](./docs/09-database-schema.md) | File-based storage in `.buildmind/` |
| [Prompt Templates](./docs/10-prompt-templates.md) | All LLM prompt templates |
| [Tech Stack](./docs/11-tech-stack.md) | Python CLI (Typer + Rich), MCP server, IDE model access |
| [MVP Build Plan](./docs/12-mvp-build-plan.md) | 7-day sprint plan |
| [Product Tiers](./docs/13-product-tiers.md) | Free / Pro / Enterprise |
| [Implementation Roadmap](./docs/14-implementation-roadmap.md) | MVP → Scale |

---

## 🚀 Quick Start

**Option A: IDE-Native (Zero Config, No API Keys)**
Connect BuildMind to your IDE's AI (like Cursor or Antigravity):
```bash
pip install buildmind
buildmind serve --mcp
```
*(See [IDE Integration Guide](./docs/15-ide-integration.md) for setup instructions)*

**Option B: Standalone CLI**
Run directly in your terminal (requires your own API key):
```bash
pip install buildmind
export ANTHROPIC_API_KEY="sk-ant-..."

# Initialize in your project
buildmind init

# Start building
buildmind start "Build whatever you're working on"
```

---

## 🏗️ Project Status

**Current Phase:** MVP Feature Complete!  
**Next Phase:** IDE Specific Plugin Wrappers / Beta Testing

See [IDE Integration Guide](./docs/15-ide-integration.md) for the full experience.  
See [MVP Build Plan](./docs/12-mvp-build-plan.md) for the 7-day build sprint.

---

*Built with 🧠 by Mukul Prasad*
