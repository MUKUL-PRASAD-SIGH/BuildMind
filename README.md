# 🧠 BuildMind

[![PyPI version](https://img.shields.io/pypi/v/buildmind.svg)](https://pypi.org/project/buildmind/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub Release](https://img.shields.io/github/v/release/MUKUL-PRASAD-SIGH/BuildMind)](https://github.com/MUKUL-PRASAD-SIGH/BuildMind/releases)
[![CI/CD](https://img.shields.io/github/actions/workflow/status/MUKUL-PRASAD-SIGH/BuildMind/publish.yml?label=PyPI%20publish)](https://github.com/MUKUL-PRASAD-SIGH/BuildMind/actions)

> **AI Thinking Infrastructure** — the operating system for human-AI collaborative engineering.
> Uses the novel **Inverted MCP Architecture** to orchestrate your entire project lifecycle with zero API keys.

```
Human     = Strategy   (you make architectural decisions at decision gates)
AI        = Execution  (code generation via your IDE's own model — zero API keys)
BuildMind = Brain      (owns the DAG, fires LLM sampling back through the IDE)
```

---

## ⚡ Install

```bash
pip install buildmind
```

**That's it.** No API keys. No cloud accounts. No config files.

---

## 🚀 Quick Start — CLI

```bash
# Inside any project folder:
buildmind start "Build a REST API with JWT auth and user management"
```

BuildMind will:
1. **Decompose** your intent into a task DAG (via your IDE's LLM — no API key)
2. **Classify** each task as `HUMAN_REQUIRED` (architectural gate) or `AI_EXECUTABLE`
3. **Surface decision cards** for each human gate — options, tradeoffs, AI recommendation
4. **Generate code** for all AI tasks after your decisions are made
5. **Write files** directly to your project

**Works for any project type:**
```bash
buildmind start "Build a REST API with authentication"
buildmind start "Build a React dashboard with charts"
buildmind start "Build a CLI tool for file compression"
buildmind start "Build a Stripe payment integration"
buildmind start "Build a real-time chat system"
buildmind start "Build a microservice for email sending"
buildmind start "Build an auth system and landing page"
```

---

## 🔌 Quick Start — MCP Server (Native IDE Integration)

BuildMind exposes a full **MCP server** that plugs directly into your IDE.
Once configured, you talk to BuildMind in plain English from any AI chat panel.

### Step 1 — Add to your MCP config

**Antigravity / Cursor / Windsurf / Claude Desktop** — add to your `mcp_config.json`:

```json
{
  "mcpServers": {
    "buildmind": {
      "command": "buildmind",
      "args": ["serve", "--mcp"]
    }
  }
}
```

### Step 2 — Talk to it in your IDE

```
You:  Use BuildMind to plan a project: build a SaaS auth system with Stripe
```

```
BuildMind:  ✅ Project created: proj_a4f2b1
            📊 Task Plan (8 tasks):
              🧑 3 HUMAN decisions required
              🤖 5 AI tasks ready to execute
            ...
            Next step: call buildmind_resume to work through decisions.
```

### Available IDE Tools

| Tool | What It Does |
|---|---|
| `buildmind_start` | Decompose your intent into a DAG + classify tasks |
| `buildmind_resume` | Get the next human decision card (options + AI recommendation) |
| `buildmind_decide` | Record your choice, unlock dependent AI tasks |
| `buildmind_execute` | Generate + write all ready AI tasks to disk |
| `buildmind_status` | Show full project progress (tasks, decisions, files written) |

---

## 🏗️ The Inverted MCP Architecture

BuildMind implements a **research-grade paradigm shift** from standard MCP usage:

```
Standard MCP:  IDE owns the AI loop → calls server tools for actions
BuildMind MCP: Server owns the orchestration DAG → fires sampling/createMessage
               back to the IDE for LLM inference
```

**What this means:**
- ✅ **Zero API keys** — all LLM calls proxied through the IDE's existing authenticated connection
- ✅ **IDE-agnostic** — works with any MCP-compatible IDE (Cursor, Windsurf, Antigravity, Claude Desktop)
- ✅ **Stateful orchestration** — the DAG, tasks, and decisions persist on disk in `.buildmind/`
- ✅ **Human-in-the-loop** — enforced architectural decision gates before AI can proceed

See the [research paper](./docs/17-mcp-inverted-architecture-research.md) for full technical details.

---

## 🧩 Decision Cards — Human Gates

When BuildMind needs your input, it surfaces a structured decision card:

```
🎯 Decision Required — Task t2: Choose Auth Strategy

📝 You need to decide how sessions are managed. This shapes your entire security model.

⚙️  Options:
  [1] JWT (Stateless)
      What: JSON Web Tokens in HTTP-only cookies
      Best when: SPAs, mobile apps, microservices
      Weakness: Hard to revoke without a blacklist

  [2] Session-based (Stateful)
      What: Redis-backed server sessions
      Best when: Admin tools, banking apps
      Weakness: Requires Redis infrastructure

💡 AI Recommendation: Option 1
   Reasoning: JWT fits a REST API with a mobile/SPA frontend better
   Confidence: high

➡️  Call buildmind_decide(task_id='t2', option_number=1) to record your choice.
```

---

## 📁 What Gets Written to Your Project

```
your-project/
├── src/
│   ├── auth/
│   │   ├── jwt_service.py       ← Written by AI (used your JWT decision)
│   │   ├── routes.py            ← Written by AI
│   │   └── middleware.py        ← Written by AI
│   └── landing/
│       ├── index.html           ← Written by AI
│       └── styles.css           ← Written by AI
└── .buildmind/
    ├── project.json             ← Project metadata
    ├── tasks.json               ← Full task DAG
    ├── decisions.json           ← All your recorded choices
    ├── gates.json               ← Human gate states
    └── audit_log.jsonl          ← Complete event history
```

---

## 🧪 Testing

```bash
# 1. Pre-flight: verify all 7 research components
python tests/test_0_preflight.py

# 2. Inverted sampling: prove IDE gets sampling requests (no mocks for the IDE)
python tests/test_2_fake_session.py

# 3. JSONRPC clean: verify Rich UI doesn't corrupt MCP stdout
python tests/test_6_stdio_clean.py
```

Expected output for all three: `[PASS]`

---

## 📚 Full Documentation

| Doc | Description |
|---|---|
| [IDE Integration ⭐ START HERE](./docs/15-ide-integration.md) | MCP setup for all IDEs, full workflow |
| [Inverted MCP Research Paper](./docs/17-mcp-inverted-architecture-research.md) | The technical novelty explained |
| [MCP Tools Reference](./docs/18-mcp-tools-reference.md) | All 5 tools, args, and return values |
| [Testing Guide](./docs/TESTING-GUIDE.md) | 8 test scenarios, full checklist |
| [PyPI Release Notes](./docs/19-pypi-release.md) | Version history and roadmap |
| [System Architecture](./docs/02-system-architecture.md) | Full DAG-based design |
| [Decision Engine](./docs/04-decision-engine.md) | How decision cards are generated |
| [Task Decomposer](./docs/03-task-decomposer.md) | How intent becomes a task DAG |
| [Router & Model Strategy](./docs/06-router-and-model-strategy.md) | IDE model selection logic |

---

## 🗺️ Roadmap

| Version | Status | What's In It |
|---|---|---|
| `0.1.0` | ✅ Released | Inverted MCP Architecture, CLI, 5 MCP tools, disk persistence |
| `0.2.0` | ✅ Released | PyPI metadata, badges, classifiers, `mcp`/`anyio` as core deps |
| `0.3.0` | 🔜 Planned | Streaming sampling tokens, multi-project support |
| `0.4.0` | 🔜 Planned | IDE-native UI panels for decision cards |
| `1.0.0` | 🔜 Planned | Stable API, full test coverage, plugin system |

---

## 🛠️ CI/CD — Automated PyPI Publishing

Every GitHub release automatically publishes to PyPI in **~42 seconds** via:
- GitHub Actions + PyPI Trusted Publisher (OIDC) — zero tokens stored anywhere
- See [`.github/workflows/publish.yml`](./.github/workflows/publish.yml)

To release a new version:
```bash
# 1. Bump version in pyproject.toml
# 2. git commit + push
# 3. Create GitHub release → published automatically
```

---

## 🤝 Contributing

```bash
git clone https://github.com/MUKUL-PRASAD-SIGH/BuildMind.git
cd BuildMind
pip install -e ".[dev]"

# Run tests
python tests/test_0_preflight.py
python tests/test_2_fake_session.py
python tests/test_6_stdio_clean.py
```

---

*Built with 🧠 by [Mukul Prasad](https://github.com/MUKUL-PRASAD-SIGH)*  
*Architecture: Inverted MCP — where the server owns the brain, not the IDE.*
