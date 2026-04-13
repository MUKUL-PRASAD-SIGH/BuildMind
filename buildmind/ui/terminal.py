"""
Rich terminal UI helpers for BuildMind.
All output styling lives here — import this, don't use Rich directly in core logic.

Windows-safe: no multi-byte emoji in print calls. Uses ASCII + Rich markup only.
"""
from __future__ import annotations

import sys
import io
from typing import Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.rule import Rule

# ── Windows UTF-8 fix ─────────────────────────────────────────────────────────
# Reconfigure stdout/stderr to UTF-8 so Rich box-drawing doesn't crash on cp1252
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Already wrapped or non-standard stream

# ── Theme ─────────────────────────────────────────────────────────────────────

THEME = Theme({
    "brand":      "bold cyan",
    "human":      "bold yellow",
    "ai":         "bold green",
    "pending":    "dim white",
    "running":    "bold blue",
    "done":       "bold green",
    "failed":     "bold red",
    "skipped":    "dim yellow",
    "warning":    "bold yellow",
    "error":      "bold red",
    "muted":      "dim white",
    "highlight":  "bold white",
    "decision":   "bold magenta",
    "gate":       "bold yellow",
    "suggestion": "italic cyan",
})

console = Console(theme=THEME)


# ── Brand header ─────────────────────────────────────────────────────────────

def print_header(subtitle: Optional[str] = None) -> None:
    console.print()
    logo = """[brand]
 ╔╗ ╦ ╦╦╦  ╔╦╗╔╦╗╦╔╗╔╔╦╗
 ╠╩╗║ ║║║   ║║║║║║║║║ ║ 
 ╚═╝╚═╝╩╩═╝═╩╝╩ ╩╩╝╚╝ ╩ 
[/brand]"""
    body = f"{logo}\n[muted]  AI Thinking Infrastructure[/muted]"
    if subtitle:
        body += f"\n  [bold cyan]{subtitle}[/bold cyan]"
        
    console.print(Panel(body, border_style="cyan", expand=False, padding=(1, 4)))
    console.print()


def print_rule(title: str = "") -> None:
    console.print(Rule(title, style="cyan"))


# ── Status badges ─────────────────────────────────────────────────────────────

STATUS_ICONS = {
    "PENDING":        ("○", "pending"),
    "AWAITING_HUMAN": ("►", "human"),
    "APPROVED":       ("✓", "done"),
    "EXECUTING":      ("↻", "running"),
    "VALIDATING":     ("⚡", "running"),
    "COMPLETED":      ("★", "done"),
    "FAILED":         ("✕", "failed"),
    "SKIPPED":        ("⏭", "skipped"),
    "UNCLASSIFIED":   ("?", "muted"),
}

TYPE_ICONS = {
    "HUMAN_REQUIRED": ("🧠", "human"),
    "AI_EXECUTABLE":  ("🤖", "ai"),
    "UNCLASSIFIED":   ("?", "muted"),
}


def status_badge(status: str) -> Text:
    icon, style = STATUS_ICONS.get(status, ("?", "muted"))
    return Text(f"{icon} {status}", style=style)


def type_badge(task_type: str) -> Text:
    icon, style = TYPE_ICONS.get(task_type, ("?", "muted"))
    return Text(f"{icon} {task_type.replace('_', ' ')}", style=style)


# ── Task table ────────────────────────────────────────────────────────────────

def print_task_table(tasks: list, title: str = "Tasks") -> None:
    """Print a Rich table of tasks."""
    table = Table(
        title=f"📋 {title}",
        box=box.SIMPLE_HEAVY,
        border_style="cyan",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("ID",         style="bold white", width=5)
    table.add_column("Type",       width=20)
    table.add_column("Status",     width=22)
    table.add_column("Title",      style="white")
    table.add_column("Deps",       style="muted", width=10)

    for task in tasks:
        table.add_row(
            task.id,
            type_badge(task.type.value if hasattr(task.type, "value") else str(task.type)),
            status_badge(task.status.value if hasattr(task.status, "value") else str(task.status)),
            task.title,
            ", ".join(task.dependencies) if task.dependencies else "—",
        )

    console.print(table)
    console.print()


# ── Decision card display ─────────────────────────────────────────────────────

def print_decision_header(task_title: str, decision_num: int, total: int) -> None:
    console.print()
    console.print(Rule(
        f"[decision]  🧩 DECISION {decision_num} of {total}  [/decision]",
        style="magenta"
    ))
    console.print(f"  [highlight]⚙️  Task:[/highlight] [white]{task_title}[/white]")
    console.print()


def print_why_human(text: str) -> None:
    console.print(Panel(
        f"[muted]{text}[/muted]",
        title="[warning]WHY YOU MUST DECIDE THIS[/warning]",
        border_style="yellow",
        padding=(0, 2),
    ))
    console.print()


def print_options(options: list, ai_suggestion_num: Optional[int] = None) -> None:
    """Print numbered decision options."""
    console.print("  [bold white]YOUR OPTIONS:[/bold white]")
    console.print()
    for opt in options:
        is_suggested = ai_suggestion_num and opt.number == ai_suggestion_num
        bullet = "[bold green]●[/bold green]" if is_suggested else "○"
        tag = "  [suggestion]<-- AI recommends[/suggestion]" if is_suggested else ""
        
        console.print(f"  {bullet} [bold white][{opt.number}][/bold white]  [bold]{opt.label}[/bold]{tag}")
        console.print(f"       [white]{opt.what_it_is}[/white]")
        console.print(f"       [muted]Best when:[/muted] {opt.best_when}")
        console.print(f"       [dim]Weakness: {opt.weakness}[/dim]")
        console.print()


def print_decision_nav() -> None:
    console.print("  [muted]Navigation:[/muted]")
    console.print("    [bold]explain <num>[/bold]    -- deeper explanation of any option")
    console.print("    [bold]compare <a> <b>[/bold]  -- side-by-side comparison")
    console.print("    [bold]why[/bold]              -- why this decision matters")
    console.print("    [bold]custom[/bold]           -- describe your own approach")
    console.print("    [bold]spec[/bold]             -- show decisions made so far")
    console.print()


def print_decision_prompt() -> str:
    return console.input("  [bold cyan]Enter choice or command:[/bold cyan] ").strip()


# ── Explanation panel ─────────────────────────────────────────────────────────

def print_explain_panel(option_label: str, detail: str) -> None:
    console.print()
    console.print(Panel(
        detail,
        title=f"[brand]  {option_label}[/brand]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print("  [muted][Press ENTER to return][/muted]")
    console.input()


# ── Messages ──────────────────────────────────────────────────────────────────

def print_success(message: str) -> None:
    console.print(f"  [done]OK  {message}[/done]")


def print_error(message: str) -> None:
    console.print(f"  [error]ERR {message}[/error]")


def print_warning(message: str) -> None:
    console.print(f"  [warning]!   {message}[/warning]")


def print_info(message: str) -> None:
    console.print(f"  [muted]i   {message}[/muted]")


def print_step(step: str, detail: str = "") -> None:
    detail_str = f"  [muted]{detail}[/muted]" if detail else ""
    console.print(f"\n  [brand]>[/brand]  [bold white]{step}[/bold white]{detail_str}")


# ── Spinner ───────────────────────────────────────────────────────────────────

def make_spinner(message: str) -> Progress:
    """Use as context manager."""
    return Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=30, style="cyan"),
        TaskProgressColumn(),
        console=console,
        transient=True,
    )


# ── Explanation Card ────────────────────────────────────────────────────────────

def print_explanation_card(exp: dict) -> None:
    """Print the component explanation panel after AI execution."""
    console.print()
    
    # Constructing the robust inner body
    body = f"\n[highlight]WHAT IT DOES[/highlight]\n──────────────────\n[white]{exp.get('what_it_does', '')}[/white]\n\n"
    body += f"[highlight]WHY IT MATTERS[/highlight]\n──────────────────\n[white]{exp.get('why_it_matters', '')}[/white]\n\n"
    
    how = exp.get("how_it_works", [])
    if how:
        body += "[highlight]HOW IT WORKS[/highlight]\n──────────────────\n"
        for i, step in enumerate(how, 1):
            body += f"  {i}. [white]{step}[/white]\n"
        body += "\n"
        
    body += f"[highlight]CODE SUMMARY[/highlight]\n──────────────────\n[muted]• {exp.get('code_summary', '')}[/muted]\n\n"
    
    watch_out = exp.get("watch_out_for", [])
    if watch_out:
        body += "[warning]WHAT TO WATCH OUT FOR[/warning]\n───────────────────────\n"
        for w in watch_out:
            body += f"  • [white]{w}[/white]\n"
            
    header_name = f" 🔍 Component: [brand]{exp.get('component_name', 'Unknown')}[/brand] "
            
    console.print(Panel(
        body,
        title=header_name,
        border_style="cyan",
        padding=(0, 2),
    ))
    console.print("  [muted][Press ENTER to continue | 's' to skip next explanations][/muted]")
    return console.input().strip().lower()


# ── Spec summary ──────────────────────────────────────────────────────────────

def print_spec(spec: dict) -> None:
    if not spec:
        console.print("  [muted]No decisions recorded yet.[/muted]")
        return
    table = Table(box=box.MINIMAL_DOUBLE_HEAD, show_header=True, header_style="bold cyan")
    table.add_column("Decision Key", style="cyan")
    table.add_column("Value", style="white")
    for key, value in spec.items():
        table.add_row(key, str(value))
    console.print(table)


# ── Project summary ───────────────────────────────────────────────────────────

def print_project_status(project, tasks: list, decisions: list) -> None:
    """Print a full project status summary."""
    print_header(f"Project: {project.title}")

    total     = len(tasks)
    completed = sum(1 for t in tasks if t.is_done)
    human     = sum(1 for t in tasks if t.is_human)
    ai_count  = sum(1 for t in tasks if t.is_ai)
    pending   = sum(1 for t in tasks if not t.is_done)

    console.print(
        f"  [muted]Total:[/muted] [white]{total}[/white]  "
        f"[done]Done: {completed}[/done]  "
        f"[pending]Pending: {pending}[/pending]  "
        f"[human][H] Human: {human}[/human]  "
        f"[ai][A] AI: {ai_count}[/ai]"
    )
    console.print(f"  [muted]Decisions:[/muted] [white]{len(decisions)}[/white]")
    console.print()

    if tasks:
        print_task_table(tasks, title=f"Tasks -- {project.id}")
