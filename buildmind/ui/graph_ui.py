"""
ASCII Task Dependency Graph UI
"""
from typing import List, Set
from rich.tree import Tree
from rich.text import Text

from buildmind.models.task import Task
from buildmind.ui.terminal import console

def _get_status_style(task: Task) -> str:
    """Return a rich style tag based on task status."""
    val = task.status.value
    if val in ("COMPLETED", "APPROVED", "SKIPPED"):
        return "green"
    elif val == "AWAITING_HUMAN":
        return "yellow bold"
    elif val == "PENDING":
        return "blue"
    elif val == "EXECUTING":
        return "cyan bold"
    elif val == "FAILED":
        return "red bold"
    return "white"

def _get_type_badge(task: Task) -> str:
    if task.is_human:
        return "[H]"
    if task.is_ai:
        return "[A]"
    return "[?]"

def _build_tree(tasks: List[Task], tree: Tree, current_task: Task, visited: Set[str]) -> None:
    # Find children: tasks that depend on current_task
    children = [t for t in tasks if current_task.id in t.dependencies]
    
    for child in children:
        # Create text label for this task
        style = _get_status_style(child)
        badge = _get_type_badge(child)
        label = Text.from_markup(f"[{style}]{badge} {child.id}: {child.title}[/{style}]")
        
        if child.id in visited:
            # Prevent deeply exponential loops and infinite recursions in case of bad DAG
            label.append(" (already printed)", style="dim")
            tree.add(label)
        else:
            visited.add(child.id)
            node = tree.add(label)
            _build_tree(tasks, node, child, visited)

def print_task_graph(tasks: List[Task]) -> None:
    """Print the entire dependency graph using rich.tree."""
    if not tasks:
        console.print("[dim]No tasks available to graph.[/dim]")
        return
        
    root_tasks = [t for t in tasks if not t.dependencies]
    
    if not root_tasks:
        console.print("[red]Warning: Zero root tasks found. Circular dependency?[/red]")
        # fallback, just pick the first task
        root_tasks = [tasks[0]]
        
    visited: Set[str] = set()
    
    console.print("")
    for root in root_tasks:
        style = _get_status_style(root)
        badge = _get_type_badge(root)
        label = Text.from_markup(f"[{style}]{badge} {root.id}: {root.title}[/{style}]")
        
        visited.add(root.id)
        tree = Tree(label)
        _build_tree(tasks, tree, root, visited)
        
        console.print(tree)
        console.print("")
