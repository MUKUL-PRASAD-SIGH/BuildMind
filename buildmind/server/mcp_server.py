"""
BuildMind MCP Server — Inverted Orchestration Architecture.

This server INVERTS the standard MCP pattern:
  - Standard MCP: IDE owns the AI loop, calls server tools for discrete actions
  - BuildMind:    Server owns the multi-step orchestration loop (DAG, tasks, decisions)
                  and fires sampling/createMessage BACK to the IDE for LLM inference

This means BuildMind requires ZERO API keys — all LLM calls are proxied through
the IDE's existing model connection via the MCP sampling protocol.

See: docs/17-mcp-inverted-architecture-research.md
"""
from __future__ import annotations

import io
import sys
import json
import contextlib
from typing import Any

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession

import buildmind.llm.client as llm_client

mcp = FastMCP(
    "BuildMind",
    instructions=(
        "BuildMind is an AI orchestration engine. It decomposes project intents into "
        "task DAGs, classifies tasks as human-decisions or AI-executable, guides you "
        "through architectural decisions, and generates code. All LLM inference is done "
        "via IDE sampling — no API keys needed.\n\n"
        "Workflow: buildmind_start → buildmind_resume (decisions) → buildmind_execute (code)"
    ),
)


def _activate_mcp_session(ctx: Context[ServerSession, None], project_dir: str = "") -> None:
    """
    Register the live MCP session into the LLM client.
    After this call, all LLMClient.complete_sync() calls in this thread
    will use sampling/createMessage to ask the IDE for completions.
    """
    if project_dir:
        import os
        try:
            os.makedirs(project_dir, exist_ok=True)
            os.chdir(project_dir)
        except Exception as e:
            pass # fallback to current dir if failing
            
    # Set both the global (for backward compat) and the ContextVar (for isolation)
    llm_client.ACTIVE_MCP_SESSION = ctx.session
    llm_client.set_mcp_session(ctx.session)


@contextlib.contextmanager  
def _silent_console():
    """Suppress Rich console output so it doesn't corrupt MCP stdio."""
    from buildmind.ui.terminal import console
    old_quiet = console.quiet
    console.quiet = True
    try:
        yield
    finally:
        console.quiet = old_quiet


def _run_cli_captured(fn, *args, **kwargs) -> tuple[str, str | None]:
    """
    Run a CLI function, capturing any stdout output.
    Returns (output_text, error_text_or_None).
    """
    buf = io.StringIO()
    err = None
    try:
        with contextlib.redirect_stdout(buf):
            fn(*args, **kwargs)
    except SystemExit:
        pass  # typer exits cleanly after most commands
    except Exception as e:
        err = str(e)
    return buf.getvalue(), err


# ── Tool: buildmind_start ─────────────────────────────────────────────────────

@mcp.tool()
def buildmind_start(intent: str, project_dir: str, ctx: Context[ServerSession, None]) -> str:
    """
    Start a new BuildMind project from your intent.

    This tool:
    1. Creates a project in .buildmind/
    2. Calls LLM (via IDE sampling) to decompose intent into a task DAG
    3. Classifies each task as HUMAN_REQUIRED or AI_EXECUTABLE
    4. Saves everything to disk

    Returns a summary of the generated task plan.
    Next step: call buildmind_resume to work through architectural decisions.
    """
    _activate_mcp_session(ctx, project_dir)

    import buildmind.cli as cli
    from buildmind.storage.project_store import load_tasks, load_project
    
    with _silent_console():
        _, err = _run_cli_captured(cli.start, intent=intent, mock=False)

    if err:
        return f"BuildMind start failed:\n{err}"

    # Read back the results from disk and return structured summary
    project = load_project()
    tasks = load_tasks()

    if not tasks:
        return "BuildMind started but no tasks were generated. Check .buildmind/ for details."

    human_tasks = [t for t in tasks if t.is_human]
    ai_tasks = [t for t in tasks if t.is_ai]

    lines = [
        f"✅ BuildMind project created: {project.id if project else 'unknown'}",
        f"📋 Intent: {intent[:80]}",
        f"",
        f"📊 Task Plan ({len(tasks)} tasks total):",
        f"  🧑 {len(human_tasks)} HUMAN decisions required",
        f"  🤖 {len(ai_tasks)} AI tasks ready to execute",
        f"",
        "Task breakdown:",
    ]
    for t in tasks:
        icon = "🧑" if t.is_human else "🤖"
        deps = f" [needs: {', '.join(t.dependencies)}]" if t.dependencies else ""
        lines.append(f"  {icon} [{t.id}] {t.title}{deps}")

    lines += [
        "",
        "Next step: call buildmind_resume to work through architectural decisions.",
    ]
    return "\n".join(lines)


# ── Tool: buildmind_resume ────────────────────────────────────────────────────

@mcp.tool()
def buildmind_resume(project_dir: str, ctx: Context[ServerSession, None]) -> str:
    """
    Resume the BuildMind project — generate decision cards for HUMAN_REQUIRED tasks.

    This tool returns a structured decision card for the next pending human decision.
    The card includes options, AI recommendation, and impact areas.

    You (the IDE/user) should review the card and call buildmind_decide with your choice.
    """
    _activate_mcp_session(ctx, project_dir)

    from buildmind.config.settings import load_config
    from buildmind.storage.project_store import load_project, load_tasks, load_decisions
    from buildmind.core.decision_engine import DecisionEngine

    project = load_project()
    if not project:
        return "❌ No BuildMind project found. Run buildmind_start first."

    tasks = load_tasks()
    if not tasks:
        return "❌ No tasks found. Run buildmind_start first."

    with _silent_console():
        config = load_config()
        engine = DecisionEngine(config=config)
        pending = engine.get_pending_tasks(tasks)

    if not pending:
        human_blocked = [t for t in tasks if t.is_human and not t.is_done]
        if not human_blocked:
            ai_ready = [t for t in tasks if t.is_ai and t.status.value == "PENDING"]
            return (
                f"✅ All decision gates resolved!\n"
                f"🤖 {len(ai_ready)} AI tasks ready.\n"
                f"Next step: call buildmind_execute to generate code."
            )
        return (
            f"⏳ {len(human_blocked)} decisions remain blocked by dependencies.\n"
            f"Complete other decisions first or call buildmind_execute for ready AI tasks."
        )

    # Generate the card for the first pending decision
    task = pending[0]
    with _silent_console():
        try:
            card = engine.generate_card(project, task, use_mock=False)
        except Exception as e:
            return f"❌ Could not generate decision card for {task.id}: {e}"

    # Format the card as structured text for the IDE to display
    lines = [
        f"🎯 Decision Required — Task {task.id}: {task.title}",
        f"",
        f"📝 Description: {task.description}",
        f"",
        f"⚙️  Options:",
    ]
    for opt in card.options:
        lines += [
            f"  [{opt.number}] {opt.label}",
            f"      What: {opt.what_it_is}",
            f"      Best when: {opt.best_when}",
            f"      Weakness: {opt.weakness}",
            f"",
        ]

    if card.ai_suggestion:
        lines += [
            f"💡 AI Recommendation: Option {card.ai_suggestion.option_number}",
            f"   Reasoning: {card.ai_suggestion.reasoning}",
            f"   Confidence: {card.ai_suggestion.confidence}",
            f"",
        ]

    if len(pending) > 1:
        lines.append(f"📌 {len(pending) - 1} more decision(s) pending after this one.")

    lines += [
        "",
        f"➡️  Call buildmind_decide(task_id='{task.id}', option_number=<N>) to record your choice.",
    ]
    return "\n".join(lines)


# ── Tool: buildmind_decide ────────────────────────────────────────────────────

@mcp.tool()
def buildmind_decide(
    task_id: str,
    option_number: int,
    project_dir: str,
    ctx: Context[ServerSession, None],
) -> str:
    """
    Record your decision for a HUMAN_REQUIRED task.

    After calling buildmind_resume to see the decision card,
    call this with the task_id and the option number you choose.
    """
    _activate_mcp_session(ctx, project_dir)

    from buildmind.config.settings import load_config
    from buildmind.storage.project_store import (
        load_project, load_tasks, load_decisions, load_gates, update_gate,
    )
    from buildmind.core.decision_engine import DecisionEngine
    from buildmind.models.task import TaskStatus
    from buildmind.storage.project_store import update_task

    project = load_project()
    if not project:
        return "❌ No project found. Run buildmind_start first."

    tasks = load_tasks()
    task = next((t for t in tasks if t.id == task_id), None)
    if not task:
        return f"❌ Task '{task_id}' not found."

    with _silent_console():
        config = load_config()
        engine = DecisionEngine(config=config)
        card = engine.generate_card(project, task, use_mock=False)

    # Find the chosen option
    chosen = next((o for o in card.options if o.number == option_number), None)
    if not chosen:
        valid = [o.number for o in card.options]
        return f"❌ Option {option_number} not valid. Valid options: {valid}"

    # Record the decision
    gate = engine.create_gate(project, task, card)
    from buildmind.models.decision import GateStatus
    gate.status = GateStatus.DECIDED
    gate.chosen_option_id = chosen.id
    gate.chosen_option_label = chosen.label
    update_gate(gate)

    # Mark task as decided and unlock dependents
    task.status = TaskStatus.DONE
    update_task(task)

    # Find tasks that are now unblocked
    updated_tasks = load_tasks()
    newly_ready = [
        t for t in updated_tasks
        if t.is_ai and t.status.value == "PENDING"
        and all(dep in {tt.id for tt in updated_tasks if tt.is_done} for dep in t.dependencies)
    ]

    return (
        f"✅ Decision recorded: Task {task_id} → Option {option_number} ({chosen.label})\n"
        f"🤖 {len(newly_ready)} AI task(s) now unblocked.\n"
        f"Call buildmind_resume for the next decision or buildmind_execute to run AI tasks."
    )


# ── Tool: buildmind_execute ───────────────────────────────────────────────────

@mcp.tool()
def buildmind_execute(project_dir: str, ctx: Context[ServerSession, None]) -> str:
    """
    Execute all ready AI tasks — generates and writes code files.

    For each PENDING AI task whose dependencies are complete:
    1. Calls LLM (via IDE sampling) with full context + spec + task description
    2. Parses the generated file list
    3. Writes files to disk

    Returns a summary of all files written.
    """
    _activate_mcp_session(ctx, project_dir)

    from buildmind.config.settings import load_config
    from buildmind.storage.project_store import (
        load_project, load_tasks, update_task, load_spec,
    )
    from buildmind.core.executor import Executor
    from buildmind.core.file_writer import write_files
    from buildmind.models.task import TaskStatus

    project = load_project()
    if not project:
        return "❌ No project found. Run buildmind_start first."

    tasks = load_tasks()
    with _silent_console():
        config = load_config()
        executor = Executor(config)
        ready = executor.get_ready_tasks(tasks)

    if not ready:
        pending_human = [t for t in tasks if t.is_human and not t.is_done]
        if pending_human:
            return (
                f"⏳ No AI tasks ready — {len(pending_human)} human decision(s) blocking.\n"
                f"Call buildmind_resume to complete decisions first."
            )
        return "✅ All tasks complete! No pending AI work."

    total = len(ready)
    results = [f"🤖 Executing {total} AI task(s)...", ""]

    for task in ready:
        results.append(f"⚙️  [{task.id}] {task.title}")
        try:
            with _silent_console():
                file_actions = executor.execute_task(project, task, use_mock=False)
            write_files(file_actions)

            task.status = TaskStatus.DONE
            update_task(task)

            for fa in file_actions:
                results.append(f"   ✅ {fa.action}: {fa.path}")
        except Exception as e:
            task.status = TaskStatus.FAILED if hasattr(TaskStatus, "FAILED") else task.status
            update_task(task)
            results.append(f"   ❌ Failed: {e}")

    results += [
        "",
        f"✅ Execution complete. {sum(1 for r in results if '✅' in r)} file(s) written.",
        "Call buildmind_status to see full project state.",
    ]
    return "\n".join(results)


# ── Tool: buildmind_status ────────────────────────────────────────────────────

@mcp.tool()
def buildmind_status(project_dir: str, ctx: Context[ServerSession, None]) -> str:
    """
    Show current BuildMind project status — tasks, decisions, and progress.
    """
    _activate_mcp_session(ctx, project_dir)

    from buildmind.storage.project_store import load_project, load_tasks, load_decisions

    project = load_project()
    if not project:
        return "❌ No project found. Run buildmind_start first."

    tasks = load_tasks()
    decisions = load_decisions()

    if not tasks:
        return f"Project: {project.id}\nNo tasks yet. Run buildmind_start."

    total = len(tasks)
    done = sum(1 for t in tasks if t.is_done)
    human_done = sum(1 for t in tasks if t.is_human and t.is_done)
    human_total = sum(1 for t in tasks if t.is_human)
    ai_done = sum(1 for t in tasks if t.is_ai and t.is_done)
    ai_total = sum(1 for t in tasks if t.is_ai)

    lines = [
        f"📊 BuildMind Status — {project.id}",
        f"🎯 Intent: {project.intent[:80]}",
        f"",
        f"Progress: {done}/{total} tasks complete",
        f"  🧑 Human decisions: {human_done}/{human_total}",
        f"  🤖 AI tasks: {ai_done}/{ai_total}",
        f"",
        "Task List:",
    ]

    status_icon = {
        "DONE": "✅",
        "PENDING": "⏳",
        "AWAITING_HUMAN": "🧑",
        "RUNNING": "🔄",
        "FAILED": "❌",
        "SKIPPED": "⏭️",
    }

    for t in tasks:
        icon = status_icon.get(t.status.value, "❓")
        deps = f" [deps: {', '.join(t.dependencies)}]" if t.dependencies else ""
        lines.append(f"  {icon} [{t.id}] {t.title}{deps}")

    if decisions:
        lines += ["", f"Decisions made ({len(decisions)}):" ]
        for d in decisions[-5:]:  # last 5
            lines.append(f"  ✅ {d.get('task_id', '?')}: {d.get('chosen_option_label', '?')}")

    return "\n".join(lines)


# ── Server entry point ────────────────────────────────────────────────────────

def start_mcp_server() -> None:
    """
    Start the BuildMind FastMCP server on stdio.

    All console output from Rich is silenced during tool execution
    to prevent corrupting the JSONRPC wire format.
    FastMCP handles the protocol framing internally.
    """
    mcp.run()


if __name__ == "__main__":
    start_mcp_server()
