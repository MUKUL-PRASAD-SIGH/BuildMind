"""
BuildMind CLI -- entry point.

Commands:
  buildmind init          Initialize BuildMind in current directory
  buildmind start "..."   Start a new project from intent
  buildmind status        Show current project status
  buildmind continue      Resume a paused project
  buildmind graph         Show ASCII task dependency graph
  buildmind decisions     Show all recorded decisions
  buildmind export        Export summary or spec
  buildmind retry <tid>   Re-run a specific task
  buildmind override <tid> Re-decide + cascade re-run
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List, Set

from buildmind.models.task import Task, TaskStatus

# Auto-load .env before anything else
try:
    from dotenv import load_dotenv
    _env_path = Path.cwd() / ".env"
    if not _env_path.exists():
        for parent in Path.cwd().parents:
            candidate = parent / ".env"
            if candidate.exists():
                _env_path = candidate
                break
    load_dotenv(_env_path, override=False)
except ImportError:
    pass

import typer
from rich.panel import Panel

from buildmind import __version__
from buildmind.config.settings import (
    is_initialized, load_config, write_default_config, get_buildmind_dir,
)
from buildmind.storage.project_store import (
    load_project, load_tasks, load_decisions, load_spec, initialize_storage,
    save_tasks,
)
from buildmind.storage.audit_log import log_project_created
from buildmind.ui.terminal import (
    console, print_header, print_success, print_error, print_warning,
    print_info, print_step, print_project_status, print_spec, print_task_table,
    make_spinner,
)

# ── App setup ─────────────────────────────────────────────────────────────────

app = typer.Typer(
    name="buildmind",
    help="BuildMind -- AI Thinking Infrastructure for human-AI collaborative engineering.",
    add_completion=False,
    rich_markup_mode="rich",
)


def _require_init() -> bool:
    if not is_initialized():
        print_error("No BuildMind project found in this directory.")
        print_info("Run [bold]buildmind init[/bold] to initialize one.")
        raise typer.Exit(1)
    return True


# ── Commands ──────────────────────────────────────────────────────────────────

@app.command()
def init(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Project name"),
    cwd: Optional[Path] = typer.Option(None, "--cwd", help="Project directory (default: current)"),
) -> None:
    """Initialize BuildMind in the current directory. No API keys required."""
    project_dir = cwd or Path.cwd()

    if is_initialized(project_dir):
        print_warning("BuildMind is already initialized in this directory.")
        print_info(f"Config: [bold]{get_buildmind_dir(project_dir) / 'config.yaml'}[/bold]")
        raise typer.Exit(0)

    print_header("Initializing BuildMind")

    bm_dir = initialize_storage(project_dir)
    print_step("Created", str(bm_dir))

    project_name = name or project_dir.resolve().name
    write_default_config(project_name, project_dir)
    print_step("Config written", str(bm_dir / "config.yaml"))

    console.print()
    console.print(Panel(
        f"[bold white]Project:[/bold white] {project_name}\n"
        f"[bold white]Models:[/bold white]  IDE models (Antigravity) -- no API keys needed\n"
        f"[bold white]Storage:[/bold white] [cyan]{bm_dir}[/cyan]\n\n"
        f"[muted]Run:[/muted] [bold cyan]buildmind start \"What do you want to build?\"[/bold cyan]",
        title="[brand]BuildMind Ready[/brand]",
        border_style="green",
        padding=(1, 2),
    ))


@app.command()
def start(
    intent: str = typer.Argument(..., help="What you want to build -- in plain English"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Decompose + classify only, no execution"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Approve each step manually"),
    mock: bool = typer.Option(False, "--mock", help="Use sample tasks -- no API key needed (for testing)"),
) -> None:
    """
    Start a new BuildMind project from your intent.

    Examples:
      buildmind start "Build a REST API with authentication"
      buildmind start "Build a Stripe payment integration"
      buildmind start "Build a REST API" --mock   (test without API key)
    """
    _require_init()
    config = load_config()

    print_header(f"Starting: {intent[:60]}...")

    from buildmind.models.project import Project, ProjectMode
    from buildmind.models.task import Task, TaskType, TaskSubType, TaskStatus, TaskComplexity
    from buildmind.storage.project_store import save_project, save_tasks
    from buildmind.storage.audit_log import log_tasks_decomposed, log_task_classified
    from buildmind.core.task_decomposer import TaskDecomposer
    from buildmind.core.decision_classifier import DecisionClassifier

    # Create project
    project_dir = Path.cwd()
    project = Project.from_intent(intent, project_dir)
    try:
        project.mode = ProjectMode(config.mode)
    except (ValueError, AttributeError):
        pass
    save_project(project)
    log_project_created(project.id, intent)
    print_step("Project created", project.id)

    if mock:
        # ── Mock path: no LLM, fixed sample tasks ─────────────────────────
        print_warning("MOCK mode -- sample tasks, no model called")
        tasks = [
            Task(id="t1", project_id=project.id,
                 title="Choose tech stack and architecture pattern",
                 description="Decide language, framework, and architecture pattern.",
                 type=TaskType.HUMAN_REQUIRED, sub_type=TaskSubType.UNKNOWN,
                 status=TaskStatus.AWAITING_HUMAN, complexity=TaskComplexity.HIGH,
                 dependencies=[],
                 classification_reason="Architecture tradeoff requires human judgment"),
            Task(id="t2", project_id=project.id,
                 title="Choose authentication strategy",
                 description="Decide between JWT, session-based, OAuth2, or API key auth.",
                 type=TaskType.HUMAN_REQUIRED, sub_type=TaskSubType.UNKNOWN,
                 status=TaskStatus.AWAITING_HUMAN, complexity=TaskComplexity.HIGH,
                 dependencies=["t1"],
                 classification_reason="Auth strategy has security and UX tradeoffs"),
            Task(id="t3", project_id=project.id,
                 title="Choose database and ORM",
                 description="Select database and whether to use ORM or raw queries.",
                 type=TaskType.HUMAN_REQUIRED, sub_type=TaskSubType.UNKNOWN,
                 status=TaskStatus.AWAITING_HUMAN, complexity=TaskComplexity.MEDIUM,
                 dependencies=["t1"],
                 classification_reason="DB choice depends on scale and team preferences"),
            Task(id="t4", project_id=project.id,
                 title="Implement data models and schema",
                 description="Create core data models: users, tasks, sessions.",
                 type=TaskType.AI_EXECUTABLE, sub_type=TaskSubType.CODE_PYTHON,
                 status=TaskStatus.PENDING, complexity=TaskComplexity.MEDIUM,
                 dependencies=["t1", "t3"],
                 classification_reason="Standard once stack is decided"),
            Task(id="t5", project_id=project.id,
                 title="Implement authentication endpoints",
                 description="Build register, login, logout, token refresh endpoints.",
                 type=TaskType.AI_EXECUTABLE, sub_type=TaskSubType.CODE_PYTHON,
                 status=TaskStatus.PENDING, complexity=TaskComplexity.HIGH,
                 dependencies=["t2", "t4"],
                 classification_reason="Clear spec once auth strategy chosen"),
            Task(id="t6", project_id=project.id,
                 title="Implement task CRUD API endpoints",
                 description="Build create, read, update, delete endpoints.",
                 type=TaskType.AI_EXECUTABLE, sub_type=TaskSubType.CODE_PYTHON,
                 status=TaskStatus.PENDING, complexity=TaskComplexity.MEDIUM,
                 dependencies=["t4", "t5"],
                 classification_reason="Standard CRUD with auth middleware"),
            Task(id="t7", project_id=project.id,
                 title="Implement input validation and error handling",
                 description="Add request validation and meaningful HTTP error codes.",
                 type=TaskType.AI_EXECUTABLE, sub_type=TaskSubType.CODE_PYTHON,
                 status=TaskStatus.PENDING, complexity=TaskComplexity.MEDIUM,
                 dependencies=["t5", "t6"],
                 classification_reason="Standard validation patterns"),
            Task(id="t8", project_id=project.id,
                 title="Write API documentation",
                 description="Generate OpenAPI/Swagger docs or README with usage examples.",
                 type=TaskType.AI_EXECUTABLE, sub_type=TaskSubType.DOCUMENTATION,
                 status=TaskStatus.PENDING, complexity=TaskComplexity.LOW,
                 dependencies=["t6", "t7"],
                 classification_reason="Documentation of existing endpoints"),
        ]
        save_tasks(tasks)
        log_tasks_decomposed(project.id, len(tasks))
        for t in tasks:
            log_task_classified(project.id, t.id, t.type.value, t.classification_reason or "")
        human_count = sum(1 for t in tasks if t.is_human)
        ai_count    = sum(1 for t in tasks if t.is_ai)
        print_success(f"Created {len(tasks)} sample tasks -- [H] {human_count} human  [A] {ai_count} AI")

    else:
        # ── Real path: LLM decompose + classify ───────────────────────────
        from buildmind.ui.terminal import make_spinner
        
        with make_spinner(f"Decomposing with {config.models.decomposer}...") as progress:
            task_id = progress.add_task(f"Decomposing with {config.models.decomposer}...", total=None)
            try:
                decomposer = TaskDecomposer(config)
                tasks = decomposer.decompose(project)
            except EnvironmentError as e:
                print_error(str(e))
                raise typer.Exit(1)
            except Exception as e:
                print_error(f"Decomposition failed: {e}")
                raise typer.Exit(1)
            progress.update(task_id, completed=100)
            
        print_success(f"Decomposed into {len(tasks)} tasks")

        with make_spinner(f"Classifying with {config.models.classifier}...") as progress:
            task_id = progress.add_task(f"Classifying with {config.models.classifier}...", total=None)
            try:
                classifier = DecisionClassifier(config)
                tasks = classifier.classify(project, tasks)
            except Exception as e:
                print_error(f"Classification failed: {e}")
                raise typer.Exit(1)
            progress.update(task_id, completed=100)
            
        human_count = sum(1 for t in tasks if t.is_human)
        ai_count    = sum(1 for t in tasks if t.is_ai)
        print_success(f"Classified -- [H] {human_count} human decisions  [A] {ai_count} AI tasks")

    # ── Show results ──────────────────────────────────────────────────────────
    console.print()
    print_task_table(tasks, title=f"Task Plan -- {project.id}")

    if dry_run:
        print_info("Dry run complete. No code written.")
        return

    print_info("Run [bold]buildmind continue[/bold] to work through decisions and execute tasks.")


@app.command()
def status() -> None:
    """Show the current project status -- tasks, decisions, and build progress."""
    _require_init()

    project = load_project()
    if not project:
        print_warning("No project started yet.")
        print_info("Run [bold]buildmind start \"...\"[/bold] to begin.")
        raise typer.Exit(0)

    tasks     = load_tasks()
    decisions = load_decisions()
    print_project_status(project, tasks, decisions)


@app.command()
def resume(
    mock: bool = typer.Option(False, "--mock", help="Use mock decision cards (no API key needed)"),
) -> None:
    """
    Resume a project -- work through decision gates interactively.

    For each HUMAN_REQUIRED task (in dependency order):
      - Shows a decision card with options, AI suggestion, and impact areas
      - Accepts: number, explain <n>, compare <a> <b>, why, custom, spec, skip
    """
    _require_init()

    project = load_project()
    if not project:
        print_warning("No project started yet.")
        print_info("Run [bold]buildmind start \"...\"[/bold] first.")
        raise typer.Exit(0)

    tasks = load_tasks()
    if not tasks:
        print_warning("No tasks found. Run [bold]buildmind start \"...\"[/bold] first.")
        raise typer.Exit(0)

    from buildmind.core.decision_engine import DecisionEngine
    from buildmind.ui.decision_ui import run_decision_card

    engine = DecisionEngine(config=load_config())
    pending = engine.get_pending_tasks(tasks)

    if not pending:
        # Check if all human tasks are already done
        human_pending = [t for t in tasks if t.is_human and not t.is_done]
        if not human_pending:
            print_success("All decision gates resolved.")
            print_info("Run [bold]buildmind status[/bold] to see the full task plan.")
        else:
            print_info("Waiting on dependent decisions first.")
            print_task_table(human_pending, title="Blocked Decisions")
        raise typer.Exit(0)

    total = len(pending)
    print_header(f"Decision Mode -- {total} decision(s) to make")
    console.print(
        f"  [muted]Project:[/muted] [white]{project.title[:70]}[/white]\n"
        f"  [muted]Working through:[/muted] [bold cyan]{total} HUMAN_REQUIRED task(s)[/bold cyan]\n"
    )

    for i, task in enumerate(pending, start=1):
        # Generate decision card
        print_info(f"Generating decision card for: [bold]{task.title}[/bold]...")
        try:
            card = engine.generate_card(project, task, use_mock=mock)
        except Exception as e:
            print_error(f"Could not generate card for {task.id}: {e}")
            print_info("Skipping. Run again or use --mock to test without API key.")
            continue

        gate = engine.create_gate(project, task, card)

        # Run interactive decision loop
        run_decision_card(
            project_id=project.id,
            task=task,
            gate=gate,
            card=card,
            decision_num=i,
            total_decisions=total,
        )

        # Reload tasks to reflect status updates
        tasks = load_tasks()
        # Refresh pending list
        pending_remaining = engine.get_pending_tasks(tasks)
        if not pending_remaining and i < total:
            print_info("Remaining decisions are blocked by dependencies. Run again after executing AI tasks.")
            break

    # Final summary
    console.print()
    all_tasks = load_tasks()
    all_decisions = load_decisions()
    print_project_status(project, all_tasks, all_decisions)

    ai_ready = [t for t in all_tasks if t.is_ai and t.status.value == "PENDING"]
    if ai_ready:
        print_info(f"[bold]{len(ai_ready)} AI tasks[/bold] ready to execute.")


@app.command()
def execute(
    mock: bool = typer.Option(False, "--mock", help="Use mock code generation (no API key needed)"),
) -> None:
    """Execute AI tasks -- generate and write code for PENDING tasks."""
    _require_init()
    
    project = load_project()
    if not project:
        print_warning("No project started yet.")
        raise typer.Exit(0)
        
    tasks = load_tasks()
    if not tasks:
        print_warning("No tasks found.")
        raise typer.Exit(0)
        
    from buildmind.core.executor import Executor
    from buildmind.core.explanation_engine import ExplanationEngine
    from buildmind.core.file_writer import write_files
    from buildmind.storage.project_store import update_task, save_tasks, load_spec
    from buildmind.models.task import TaskStatus
    from buildmind.ui.terminal import print_explanation_card
    
    config = load_config()
    executor = Executor(config)
    explainer = ExplanationEngine(config)
    
    executed_any = False
    skip_explanations = False
    
    while True:
        ready_tasks = executor.get_ready_tasks(load_tasks())
        
        if not ready_tasks:
            break
            
        total = len(ready_tasks)
        print_header(f"Execution Mode -- {total} task(s) ready")
        spec = load_spec()
        
        for i, task in enumerate(ready_tasks, start=1):
            print_step(f"Executing [{i}/{total}]: {task.title}...")
            try:
                from buildmind.ui.terminal import make_spinner
                with make_spinner("Writing code...") as progress:
                    pid = progress.add_task(f"Generating for {task.id}", total=None)
                    file_actions = executor.execute_task(project, task, use_mock=mock)
                    write_files(Path.cwd(), file_actions)
                    progress.update(pid, completed=100)
                    
                task.status = TaskStatus.COMPLETED
                update_task(task)
                executed_any = True
                print_success(f"Task {task.id} complete.")
                
                # Explanation Engine
                if not skip_explanations:
                    with make_spinner("Explaining component...") as progress:
                        pid = progress.add_task(f"Analyzing {task.id}...", total=None)
                        explanation_json = explainer.generate_component_explanation(
                            project, task, file_actions, spec, use_mock=mock
                        )
                        progress.update(pid, completed=100)
                    
                    user_input = print_explanation_card(explanation_json)
                    if user_input and user_input.startswith("s"):
                        skip_explanations = True
                
            except Exception as e:
                print_error(f"Failed to execute {task.id}: {e}")
                print_info("Skipping to next task...")
                continue
                
    if not executed_any:
        tasks = load_tasks()
        pending_ai = [t for t in tasks if t.is_ai and not t.is_done]
        if pending_ai:
            print_warning("AI tasks exist but are blocked by dependencies (e.g. AWAITING_HUMAN gates).")
            print_info("Run [bold]buildmind resume[/bold] to clear decisions first.")
        else:
            print_success("All AI tasks are complete.")
        raise typer.Exit(0)
            
    console.print()
    all_tasks = load_tasks()
    print_project_status(project, all_tasks, load_decisions())
    


@app.command()
def graph() -> None:
    """Show the task dependency graph as ASCII in your terminal."""
    _require_init()
    
    tasks = load_tasks()
    if not tasks:
        print_warning("No tasks found. Start a project first.")
        raise typer.Exit(0)
        
    project = load_project()
    print_header(f"Task Graph -- {project.title[:50]}...")
    
    from buildmind.ui.graph_ui import print_task_graph
    print_task_graph(tasks)


@app.command()
def decisions() -> None:
    """Show all decisions you have made in this project."""
    _require_init()

    all_decisions = load_decisions()
    spec = load_spec()

    if not all_decisions:
        print_info("No decisions recorded yet.")
        return

    print_header("Decisions Made")
    print_spec(spec)

    console.print(f"\n  [muted]Total:[/muted] [white]{len(all_decisions)} decision(s)[/white]")
    for d in all_decisions:
        accepted = " [suggestion](AI suggestion)[/suggestion]" if d.accepted_ai_suggestion else ""
        console.print(
            f"  [bold white]{d.task_id}[/bold white]  "
            f"-->  [cyan]{d.chosen_value}[/cyan]{accepted}"
        )


def _get_descendants(tasks: List[Task], target_id: str) -> Set[str]:
    """Find all task IDs that depend on target_id recursively."""
    descendants = set()
    queue = [target_id]
    while queue:
        curr = queue.pop(0)
        for t in tasks:
            if curr in t.dependencies and t.id not in descendants:
                descendants.add(t.id)
                queue.append(t.id)
    return descendants


@app.command()
def retry(
    task_id: str = typer.Argument(..., help="Task ID to retry, e.g. t3"),
) -> None:
    """Re-run a specific AI task and cascade reset its dependents."""
    _require_init()
    
    tasks = load_tasks()
    target = next((t for t in tasks if t.id == task_id), None)
    
    if not target:
        print_error(f"Task '{task_id}' not found.")
        raise typer.Exit(1)
        
    if target.is_human:
        print_error(f"Task {task_id} is a human decision task. Use 'buildmind override {task_id}' instead.")
        raise typer.Exit(1)
        
    descendants = _get_descendants(tasks, task_id)
    
    target.status = TaskStatus.PENDING
    reset_count = 1
    
    for t in tasks:
        if t.id in descendants and t.is_ai:
            t.status = TaskStatus.PENDING
            reset_count += 1
            
    save_tasks(tasks)
    print_success(f"Reset {reset_count} AI task(s) to PENDING (including descendants).")
    print_info("Run [bold]buildmind execute[/bold] to process them.")


@app.command()
def override(
    task_id: str = typer.Argument(..., help="Task ID to re-decide, e.g. t1"),
) -> None:
    """Re-decide a HUMAN task and cascade reset all affected tasks."""
    _require_init()
    
    tasks = load_tasks()
    target = next((t for t in tasks if t.id == task_id), None)
    
    if not target:
        print_error(f"Task '{task_id}' not found.")
        raise typer.Exit(1)
        
    if target.is_ai:
        print_error(f"Task {task_id} is an AI task. Use 'buildmind retry {task_id}' instead.")
        raise typer.Exit(1)
        
    descendants = _get_descendants(tasks, task_id)
    
    # 1. Reset Tasks
    target.status = TaskStatus.AWAITING_HUMAN
    reset_human = 1
    reset_ai = 0
    
    for t in tasks:
        if t.id in descendants:
            if t.is_human:
                t.status = TaskStatus.AWAITING_HUMAN
                reset_human += 1
            else:
                t.status = TaskStatus.PENDING
                reset_ai += 1
    save_tasks(tasks)
    
    # 2. Clear Decisions & Spec
    decisions = load_decisions()
    to_delete_ids = descendants.copy()
    to_delete_ids.add(task_id)
    
    new_decisions = [d for d in decisions if d.task_id not in to_delete_ids]
    
    from buildmind.storage.project_store import save_decisions, save_spec
    save_decisions(new_decisions)
    
    # Rebuild spec from remaining decisions
    new_spec = {}
    task_map = {t.id: t for t in load_tasks()}
    for d in new_decisions:
        t = task_map.get(d.task_id)
        if t:
            # Need to match the same logic as _record_decision / _skip_decision
            if d.is_skipped:
                new_spec[d.task_id] = d.chosen_value
            else:
                skey = t.title.lower().replace(" ", "_").replace("/", "_")[:40]
                new_spec[skey] = d.chosen_value
                
    save_spec(new_spec)
    
    print_success(f"Overridden {task_id}. Cascade reset {reset_human} Human task(s) and {reset_ai} AI task(s).")
    print_info("Run [bold]buildmind resume[/bold] to re-make decisions, then [bold]buildmind execute[/bold].")


@app.command()
def serve(
    mcp: bool = typer.Option(False, "--mcp", help="Run as an MCP standard server for IDEs"),
) -> None:
    """Start the BuildMind server (for IDE MCP Integration)."""
    if not mcp:
        print_warning("Server mode currently requires the --mcp flag.")
        print_info("Use: buildmind serve --mcp")
        raise typer.Exit(1)
        
    try:
        from buildmind.server.mcp_server import start_mcp_server
        start_mcp_server()
    except ImportError:
        print_error("Failed to load the MCP server modules. Did you install with 'pip install buildmind[mcp]'?")
        raise typer.Exit(1)


@app.command()
def export(
    what: str = typer.Argument("summary", help="What to export: 'summary' or 'spec'"),
) -> None:
    """Export project summary or spec."""
    _require_init()
    if what == "spec":
        spec = load_spec()
        if not spec:
            print_info("No spec recorded yet.")
        else:
            print_spec(spec)
    elif what == "summary":
        project = load_project()
        if not project:
            print_warning("No project started yet.")
            raise typer.Exit(0)
            
        tasks = load_tasks()
        decisions = load_decisions()
        
        from buildmind.core.export_engine import ExportEngine
        engine = ExportEngine(load_config())
        
        output_path = Path("buildmind_report.md")
        engine.export_summary(project, tasks, decisions, output_path)
        
        print_success(f"Project summary exported successfully to [bold]{output_path}[/bold]")
    else:
        print_error(f"Unknown export option: '{what}'. Use 'summary' or 'spec'.")


# ── Version / root callback ───────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit"),
) -> None:
    """
    BuildMind -- AI Thinking Infrastructure

    Orchestrate human decisions and AI execution in your IDE terminal.
    Uses your IDE's AI models (no API keys required).
    """
    if version:
        console.print(f"[brand]BuildMind[/brand] [white]v{__version__}[/white]")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        print_header()
        console.print(ctx.get_help())


if __name__ == "__main__":
    app()
