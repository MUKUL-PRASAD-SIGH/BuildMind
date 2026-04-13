"""
Interactive Decision UI -- Phase 4.

Presents a DecisionCard as an interactive terminal session.
Supports: pick by number, explain <n>, compare <a> <b>, why, custom, spec, skip.

Returns a Decision object with the user's choice recorded.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from buildmind.models.decision import (
    AISuggestion, Decision, DecisionCard, DecisionOption, Gate, GateStatus,
)
from buildmind.models.task import Task, TaskStatus
from buildmind.storage.project_store import (
    append_decision, load_spec, update_spec, update_gate, update_task,
)
from buildmind.storage.audit_log import log_gate_approved, log_gate_skipped
from buildmind.ui.terminal import (
    console,
    print_rule,
    print_decision_header,
    print_why_human,
    print_options,
    print_decision_nav,
    print_decision_prompt,
    print_explain_panel,
    print_spec,
    print_success,
    print_info,
    print_warning,
)
from rich import box
from rich.panel import Panel
from rich.table import Table


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_decision_id(project_id: str, task_id: str) -> str:
    return f"dec_{hashlib.md5(f'{project_id}{task_id}'.encode()).hexdigest()[:8]}"


def _print_impact(impact_areas: list[str]) -> None:
    if not impact_areas:
        return
    console.print("  [bold white]WHAT THIS SHAPES (hard to change later):[/bold white]")
    for area in impact_areas:
        console.print(f"    [warning]>[/warning] {area}")
    console.print()


def _print_ai_banner(ai: AISuggestion) -> None:
    confidence_color = {
        "high": "green", "medium": "yellow", "low": "red"
    }.get(ai.confidence, "white")
    console.print(Panel(
        f"[suggestion]AI recommends option [{ai.option_number}][/suggestion]  "
        f"Confidence: [{confidence_color}]{ai.confidence.upper()}[/{confidence_color}]\n\n"
        f"[white]{ai.reasoning}[/white]",
        title="[brand]AI Suggestion[/brand]",
        border_style="cyan",
        padding=(0, 2),
    ))
    if ai.caveats:
        console.print("  [muted]Exceptions:[/muted]")
        for c in ai.caveats:
            console.print(f"    [dim]- {c}[/dim]")
    console.print()


def _compare_options(opts: list[DecisionOption], a: int, b: int) -> None:
    opt_a = next((o for o in opts if o.number == a), None)
    opt_b = next((o for o in opts if o.number == b), None)
    if not opt_a or not opt_b:
        print_warning(f"Invalid option numbers: {a}, {b}")
        return

    table = Table(box=box.ROUNDED, border_style="cyan", show_header=True, header_style="bold cyan")
    table.add_column("", style="bold white", width=16)
    table.add_column(f"[{a}] {opt_a.label}", style="white")
    table.add_column(f"[{b}] {opt_b.label}", style="white")

    table.add_row("What it is",   opt_a.what_it_is,  opt_b.what_it_is)
    table.add_row("Best when",    opt_a.best_when,   opt_b.best_when)
    table.add_row("Weakness",     opt_a.weakness,    opt_b.weakness)

    console.print()
    console.print(table)
    console.print()


# ── Main interactive loop ─────────────────────────────────────────────────────

def run_decision_card(
    project_id: str,
    task: Task,
    gate: Gate,
    card: DecisionCard,
    decision_num: int,
    total_decisions: int,
) -> Decision:
    """
    Present a decision card and collect user input.
    Loops until the user picks a valid option, types 'custom', or skips.
    Returns a Decision object.
    """
    ai_num = card.ai_suggestion.option_number if card.ai_suggestion else None

    while True:
        # ── Re-render the card ────────────────────────────────────────────
        print_decision_header(task.title, decision_num, total_decisions)
        _print_impact(card.impact_areas)
        print_why_human(card.why_human)

        if card.ai_suggestion:
            _print_ai_banner(card.ai_suggestion)

        print_options(card.options, ai_suggestion_num=ai_num)
        print_decision_nav()

        raw = print_decision_prompt()
        cmd = raw.lower().strip()

        # ── Command parsing ───────────────────────────────────────────────

        # Pick by number
        if cmd.isdigit():
            num = int(cmd)
            chosen = next((o for o in card.options if o.number == num), None)
            if not chosen:
                print_warning(f"No option [{num}]. Valid: 1-{len(card.options)}")
                continue
            accepted_ai = (ai_num is not None and num == ai_num)
            return _record_decision(
                project_id=project_id, task=task, gate=gate, card=card,
                chosen=chosen, accepted_ai=accepted_ai,
                mode="guided" if accepted_ai else "manual",
            )

        # explain <n>
        if cmd.startswith("explain"):
            parts = cmd.split()
            if len(parts) >= 2 and parts[1].isdigit():
                n = int(parts[1])
                opt = next((o for o in card.options if o.number == n), None)
                if opt:
                    print_explain_panel(
                        f"[{n}] {opt.label}",
                        opt.explain_detail
                    )
                else:
                    print_warning(f"No option [{n}]")
            else:
                print_warning("Usage: explain <number>  e.g. explain 2")
            continue

        # compare <a> <b>
        if cmd.startswith("compare"):
            parts = cmd.split()
            if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
                _compare_options(card.options, int(parts[1]), int(parts[2]))
            else:
                print_warning("Usage: compare <a> <b>  e.g. compare 1 3")
            continue

        # why
        if cmd == "why":
            console.print()
            console.print(Panel(
                card.why_human,
                title="[warning]Why you must decide this[/warning]",
                border_style="yellow", padding=(1, 2),
            ))
            console.print()
            continue

        # spec
        if cmd == "spec":
            console.print()
            console.print("[bold white]Decisions made so far:[/bold white]")
            print_spec(load_spec())
            console.print()
            continue

        # custom
        if cmd == "custom":
            console.print()
            console.print("  [muted]Describe your approach (press ENTER to submit):[/muted]")
            custom_val = console.input("  [bold cyan]Your choice:[/bold cyan] ").strip()
            if not custom_val:
                print_warning("Empty input -- try again or pick a numbered option.")
                continue
            # Treat as a custom option
            fake_option = DecisionOption(
                id="opt_custom",
                number=0,
                label=f"Custom: {custom_val[:40]}",
                what_it_is=custom_val,
                best_when="As specified by user",
                weakness="Not evaluated by AI",
                explain_detail=custom_val,
            )
            return _record_decision(
                project_id=project_id, task=task, gate=gate, card=card,
                chosen=fake_option, accepted_ai=False,
                custom_input=custom_val, mode="custom",
            )

        # skip
        if cmd in ("skip", "s"):
            console.print()
            reason = console.input("  [muted]Why skipping? (optional, press ENTER to skip):[/muted] ").strip()
            return _skip_decision(
                project_id=project_id, task=task, gate=gate, card=card,
                reason=reason or "User skipped"
            )

        # Unknown command
        print_warning(f"Unknown command: '{raw}'. Type a number or: explain, compare, why, custom, spec, skip")


# ── Record result ─────────────────────────────────────────────────────────────

def _record_decision(
    project_id: str,
    task: Task,
    gate: Gate,
    card: DecisionCard,
    chosen: DecisionOption,
    accepted_ai: bool,
    custom_input: Optional[str] = None,
    mode: str = "manual",
) -> Decision:
    """Persist the user's decision and update gate + task status."""
    from datetime import datetime

    decision = Decision(
        id=_make_decision_id(project_id, task.id),
        project_id=project_id,
        task_id=task.id,
        gate_id=gate.id,
        options_shown=card.options,
        ai_suggestion=card.ai_suggestion,
        chosen_option_id=chosen.id,
        chosen_option_number=chosen.number,
        chosen_value=chosen.label,
        custom_input=custom_input,
        accepted_ai_suggestion=accepted_ai,
        mode=mode,
        decided_at=datetime.utcnow(),
    )

    # Persist decision
    append_decision(decision)

    # Update spec
    spec_key = task.title.lower().replace(" ", "_").replace("/", "_")[:40]
    update_spec(spec_key, chosen.label)

    # Resolve gate
    gate.status = GateStatus.APPROVED
    gate.resolved_at = datetime.utcnow()
    update_gate(gate)

    # Mark task approved
    task.status = TaskStatus.APPROVED
    update_task(task)

    # Audit log
    log_gate_approved(project_id, task.id, chosen.label, accepted_ai)

    print_success(f"Decision recorded: [bold]{chosen.label}[/bold]")
    console.print()
    return decision


def _skip_decision(
    project_id: str,
    task: Task,
    gate: Gate,
    card: DecisionCard,
    reason: str,
) -> Decision:
    from datetime import datetime

    decision = Decision(
        id=_make_decision_id(project_id, task.id),
        project_id=project_id,
        task_id=task.id,
        gate_id=gate.id,
        options_shown=card.options,
        ai_suggestion=card.ai_suggestion,
        chosen_value="SKIPPED",
        accepted_ai_suggestion=False,
        skip_reason=reason,
        mode="manual",
        decided_at=datetime.utcnow(),
    )

    append_decision(decision)
    update_spec(task.id, "SKIPPED")

    gate.status = GateStatus.SKIPPED
    gate.resolved_at = datetime.utcnow()
    update_gate(gate)

    task.status = TaskStatus.SKIPPED
    update_task(task)

    log_gate_skipped(project_id, task.id, reason)
    print_warning(f"Skipped: {task.title}")
    console.print()
    return decision
