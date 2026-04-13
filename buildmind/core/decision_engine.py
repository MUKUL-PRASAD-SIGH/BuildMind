"""
Decision Engine -- Phase 4 core service.

For each HUMAN_REQUIRED (AWAITING_HUMAN) task:
  1. Generates a DecisionCard via LLM (or mock)
  2. Creates a Gate record
  3. Saves everything to storage

The DecisionUI (decision_ui.py) then presents the card interactively.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from buildmind.config.settings import BuildMindConfig
from buildmind.llm.client import LLMClient
from buildmind.models.decision import (
    AISuggestion, DecisionCard, DecisionOption, Gate, GateStatus,
)
from buildmind.models.project import Project
from buildmind.models.task import Task, TaskStatus
from buildmind.prompts.loader import load
from buildmind.storage.project_store import (
    load_spec, save_gates, load_gates, update_gate,
)
from buildmind.storage.audit_log import log_gate_presented


# ── JSON extraction helper ────────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_decision_card(raw_json: str, task: Task) -> DecisionCard:
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"DecisionEngine: LLM returned invalid JSON for task {task.id}.\n"
            f"Error: {e}\nRaw (first 400):\n{raw_json[:400]}"
        )

    raw_options = data.get("options", [])
    if not raw_options:
        raise ValueError(f"DecisionEngine: No options returned for task {task.id}")

    options = []
    for i, opt in enumerate(raw_options, start=1):
        options.append(DecisionOption(
            id=f"opt_{i}",
            number=opt.get("number", i),
            label=opt.get("label", f"Option {i}"),
            what_it_is=opt.get("what_it_is", ""),
            best_when=opt.get("best_when", ""),
            weakness=opt.get("weakness", ""),
            explain_detail=opt.get("explain_detail", opt.get("what_it_is", "")),
        ))

    ai_num = data.get("ai_suggestion_option")
    ai_suggestion: Optional[AISuggestion] = None
    if ai_num is not None:
        matched = next((o for o in options if o.number == ai_num), None)
        if matched:
            ai_suggestion = AISuggestion(
                option_id=matched.id,
                option_number=matched.number,
                reasoning=data.get("ai_suggestion_reasoning", ""),
                caveats=data.get("ai_suggestion_caveats", []),
                confidence=data.get("ai_suggestion_confidence", "medium"),
            )

    return DecisionCard(
        task_id=task.id,
        why_human=data.get("why_human", "This decision requires your judgment."),
        impact_areas=data.get("impact_areas", []),
        options=options,
        ai_suggestion=ai_suggestion,
        blocks_tasks=task.blocks,
    )


# ── Mock card generator ───────────────────────────────────────────────────────

def _mock_decision_card(task: Task) -> DecisionCard:
    """Generate a plausible mock decision card without calling LLM."""
    title_lower = task.title.lower()

    if "auth" in title_lower:
        options = [
            DecisionOption(id="opt_1", number=1, label="JWT (stateless)",
                what_it_is="JSON Web Tokens stored client-side, verified by signature.",
                best_when="Microservices, mobile clients, or when you need stateless horizontal scaling.",
                weakness="Cannot invalidate individual tokens without a blocklist — logout is complex.",
                explain_detail="JWT stores user claims in a signed, self-contained token. The server verifies the signature without hitting a database. This makes it perfect for distributed systems. However, once issued, a JWT is valid until expiry. Implementing true logout requires a token blocklist (which reintroduces statefulness), or very short expiry windows with refresh tokens. Best suited for SPAs and mobile apps that need to work across multiple API servers."),
            DecisionOption(id="opt_2", number=2, label="Session (stateful)",
                what_it_is="Server stores session data; client holds only a session ID cookie.",
                best_when="Traditional web apps, simple single-server deployments, or when you need instant logout.",
                weakness="Requires shared session store (Redis/DB) for horizontal scaling. Not ideal for APIs.",
                explain_detail="Session-based auth is the classic approach. The server creates a session record on login and the client stores only the session ID in a cookie. Logout instantly invalidates the session. The main scaling challenge is that all servers need access to the same session store, typically Redis. This adds infrastructure complexity but is well-understood and very secure."),
            DecisionOption(id="opt_3", number=3, label="OAuth2 + OIDC",
                what_it_is="Delegate authentication to a trusted identity provider (Google, Auth0, etc.).",
                best_when="When you want to avoid managing passwords, or need social login / SSO.",
                weakness="External dependency. Implementation complexity is high. Overkill for simple internal APIs.",
                explain_detail="OAuth2 delegates the auth responsibility to a third-party Identity Provider (IdP). Users authenticate with Google, GitHub, or a service like Auth0, and you receive a verified token. You never store passwords. The downside is vendor dependency, more complex flow, and it requires HTTPS everywhere. For a simple internal REST API, this is often over-engineered unless you specifically need social login or enterprise SSO."),
            DecisionOption(id="opt_4", number=4, label="API Keys",
                what_it_is="Long-lived secret tokens issued per client; sent in Authorization header.",
                best_when="Machine-to-machine APIs, developer APIs, or B2B integrations without user sessions.",
                weakness="No built-in expiry or refresh. Key management is the user's responsibility.",
                explain_detail="API keys are simply long random strings stored in the database (hashed). Each client/service gets one and includes it in every request. Simple to implement and understand. Works well for developer-facing APIs (like Stripe, OpenAI). The main downside is that keys are long-lived and don't auto-expire, so rotation and revocation need explicit UI/tooling."),
        ]
        ai_suggestion = AISuggestion(
            option_id="opt_1", option_number=1,
            reasoning="For a REST API with task management, JWT is the standard choice. It enables stateless scaling and works well with mobile/SPA clients. Combine with short-lived access tokens (15min) and refresh tokens stored in HttpOnly cookies for logout support.",
            caveats=["If you need instant account suspension, add a token blocklist in Redis", "If this is internal-only B2B, API Keys (option 4) may be simpler"],
            confidence="high",
        )
        return DecisionCard(
            task_id=task.id,
            why_human="Authentication strategy defines how every user session works, impacts security architecture, and is hard to change later. The right choice depends on your client types, scaling plans, and operational complexity tolerance.",
            impact_areas=["All protected API endpoints", "Token storage and refresh logic", "Logout behavior", "Horizontal scaling approach", "Mobile/web client integration"],
            options=options,
            ai_suggestion=ai_suggestion,
            blocks_tasks=task.blocks,
        )

    elif "database" in title_lower or "db" in title_lower or "orm" in title_lower:
        options = [
            DecisionOption(id="opt_1", number=1, label="PostgreSQL + ORM",
                what_it_is="PostgreSQL with SQLAlchemy/Prisma/TypeORM for schema management.",
                best_when="Most applications. Strong ACID guarantees, rich querying, proven at scale.",
                weakness="More setup than SQLite. Requires running a Postgres instance.",
                explain_detail="PostgreSQL is the default choice for most production applications. With an ORM you get schema migrations, model validation, and query building without raw SQL. SQLAlchemy (Python), Prisma (JS/TS), or TypeORM are the standard options. The ORM layer means your models are defined once in code and the schema is auto-generated. Trades some query flexibility for developer velocity."),
            DecisionOption(id="opt_2", number=2, label="PostgreSQL + raw SQL",
                what_it_is="PostgreSQL with hand-written SQL queries via a lightweight driver.",
                best_when="Performance-critical systems, complex queries, or teams that prefer explicit control.",
                weakness="No auto-migrations. More boilerplate. Schema changes require manual SQL.",
                explain_detail="Skipping the ORM and writing raw SQL gives you full control over query performance. Tools like asyncpg (Python) or pg (Node.js) let you run parameterized SQL directly. You manage schema with migration files (Flyway, Alembic, or raw .sql). This approach is preferred by teams that find ORMs generate inefficient queries or want to avoid the magic. Requires more discipline around schema versioning."),
            DecisionOption(id="opt_3", number=3, label="SQLite (dev only)",
                what_it_is="Embedded file-based database, zero infrastructure required.",
                best_when="Local development, prototyping, or single-user tools.",
                weakness="Not suitable for production with concurrent writes. No network access.",
                explain_detail="SQLite is a file-based database that requires zero infrastructure. It's perfect for local development or single-user tools. However, it does not support concurrent writes well and cannot be accessed over a network. Most teams use SQLite in development and migrate to Postgres for production, using an ORM (like SQLAlchemy) to make the swap trivial."),
            DecisionOption(id="opt_4", number=4, label="MongoDB (document)",
                what_it_is="NoSQL document database. Schema-less JSON storage.",
                best_when="Highly variable document structures, rapid prototyping, or content systems.",
                weakness="No joins, no ACID transactions across documents. Schema discipline is on you.",
                explain_detail="MongoDB stores data as JSON-like documents without a fixed schema. This makes it fast to prototype and flexible when your data structure is evolving. The downside is the lack of relational joins and limited transaction support. For a task management API with users, tasks, and relationships, a relational database usually fits better unless your task data is highly variable in structure."),
        ]
        ai_suggestion = AISuggestion(
            option_id="opt_1", option_number=1,
            reasoning="PostgreSQL with an ORM is the right default for a task management REST API. You have clear relational data (users, tasks, relationships), need ACID transactions, and will benefit from schema migrations as the project evolves.",
            caveats=["If your team writes complex SQL and wants full control, option 2 is equally valid", "If this is a quick prototype, SQLite option 3 is fine for local dev"],
            confidence="high",
        )
        return DecisionCard(
            task_id=task.id,
            why_human="Database choice affects every data operation in the system and is extremely expensive to change later. The right pick depends on your data shape, team expertise, infrastructure budget, and scaling expectations.",
            impact_areas=["Data models and schema", "Query patterns and performance", "Horizontal scaling strategy", "Backup and disaster recovery", "Local development setup"],
            options=options,
            ai_suggestion=ai_suggestion,
            blocks_tasks=task.blocks,
        )

    else:
        # Generic decision card for any other task type
        options = [
            DecisionOption(id="opt_1", number=1, label="Approach A (Minimal)",
                what_it_is="The simplest implementation that satisfies the requirement.",
                best_when="Early stages, tight timelines, or when requirements may change.",
                weakness="May need refactoring as requirements grow.",
                explain_detail="The minimal approach delivers exactly what's needed right now without over-engineering. It's faster to build, easier to understand, and easier to change. The tradeoff is that you may outgrow it and need to refactor. This is often the right default when you're still learning what the system needs to do."),
            DecisionOption(id="opt_2", number=2, label="Approach B (Standard)",
                what_it_is="The industry-standard pattern with moderate complexity.",
                best_when="Production systems with known requirements and growth expectations.",
                weakness="More upfront work. May be overkill if scope is small.",
                explain_detail="The standard approach uses established patterns and conventions. It takes more time to set up but pays off quickly as the system grows. Most experienced engineers will recognize and understand the code immediately. This is usually the right choice for any system that will live in production longer than a few months."),
            DecisionOption(id="opt_3", number=3, label="Approach C (Full)",
                what_it_is="A comprehensive, enterprise-grade implementation.",
                best_when="High-scale systems, regulated environments, or long-lived codebases.",
                weakness="Significant upfront investment. Over-engineered for simple systems.",
                explain_detail="The full approach implements every consideration: observability, extensibility, compliance, and performance. It's appropriate when you know the system will need to scale significantly and the cost of rearchitecting later is high. For most applications, this adds unnecessary complexity early and should only be chosen with clear evidence of need."),
        ]
        ai_suggestion = AISuggestion(
            option_id="opt_2", option_number=2,
            reasoning="The standard approach balances speed and maintainability for most production systems.",
            caveats=["If this is a prototype, choose option 1", "If you have specific high-scale requirements, option 3 may be justified"],
            confidence="medium",
        )
        return DecisionCard(
            task_id=task.id,
            why_human=f"'{task.title}' involves a design tradeoff that depends on your goals, constraints, and team preferences -- context that only you have.",
            impact_areas=["System architecture", "Development velocity", "Maintenance burden", "Scalability"],
            options=options,
            ai_suggestion=ai_suggestion,
            blocks_tasks=task.blocks,
        )


# ── Decision Engine ───────────────────────────────────────────────────────────

class DecisionEngine:
    """
    Generates DecisionCard objects for HUMAN_REQUIRED tasks.
    Called once per task before the interactive prompt is shown.
    """

    def __init__(self, config: BuildMindConfig):
        self.config = config
        self.llm = LLMClient(config)

    def generate_card(
        self,
        project: Project,
        task: Task,
        use_mock: bool = False,
    ) -> DecisionCard:
        """Generate a DecisionCard for a HUMAN_REQUIRED task."""
        if use_mock:
            return _mock_decision_card(task)

        spec = load_spec()
        context_str = ""
        if project.context.stack:
            context_str += f"Stack: {project.context.stack}\n"
        if project.context.constraints:
            context_str += f"Constraints: {project.context.constraints}\n"

        system_prompt = load("decision_card_system")
        user_prompt = load(
            "decision_card_user",
            project_id=project.id,
            intent=project.intent,
            context=context_str or "Not specified",
            spec_json=json.dumps(spec, indent=2) if spec else "{}",
            task_id=task.id,
            task_title=task.title,
            task_description=task.description,
        )

        raw = self.llm.complete_sync(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=self.config.models.decision_card,
            max_tokens=3000,
            temperature=0.3,
            json_mode=True,
        )
        raw_clean = _extract_json(raw)
        return _parse_decision_card(raw_clean, task)

    def create_gate(self, project: Project, task: Task, card: DecisionCard) -> Gate:
        """Create and persist a Gate record for a decision card."""
        from datetime import datetime
        import hashlib
        gate_id = f"gate_{hashlib.md5(f'{project.id}{task.id}'.encode()).hexdigest()[:8]}"
        gate = Gate(
            id=gate_id,
            project_id=project.id,
            task_id=task.id,
            status=GateStatus.AWAITING_HUMAN,
            blocks_tasks=task.blocks,
            decision_card=card,
            presented_at=datetime.utcnow(),
        )
        gates = load_gates()
        # Replace if already exists
        existing_ids = [g.id for g in gates]
        if gate.id in existing_ids:
            gates = [gate if g.id == gate.id else g for g in gates]
        else:
            gates.append(gate)
        save_gates(gates)
        log_gate_presented(project.id, task.id, len(card.options))
        return gate

    def get_pending_tasks(self, tasks: list[Task]) -> list[Task]:
        """Return AWAITING_HUMAN tasks in dependency-safe order."""
        completed = {t.id for t in tasks if t.is_done}
        return [
            t for t in tasks
            if t.status.value == "AWAITING_HUMAN"
            and t.can_execute(completed)
        ]
