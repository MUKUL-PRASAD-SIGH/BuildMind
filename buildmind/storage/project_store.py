"""
File-based storage for BuildMind.
All state lives in .buildmind/ inside the user's project directory.
No database required.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from buildmind.config.settings import get_buildmind_dir
from buildmind.models.project import Project
from buildmind.models.task import Task
from buildmind.models.decision import Decision, Gate


# ── File name constants ──────────────────────────────────────────────────────
PROJECT_FILE   = "project.json"
TASKS_FILE     = "tasks.json"
DECISIONS_FILE = "decisions.json"
GATES_FILE     = "gates.json"
SPEC_FILE      = "spec.json"
GRAPH_FILE     = "graph.json"
OUTPUTS_DIR    = "outputs"


def _bm_dir(cwd: Optional[Path] = None) -> Path:
    return get_buildmind_dir(cwd)


def _read_json(path: Path) -> dict | list:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


# ── Project ──────────────────────────────────────────────────────────────────

def save_project(project: Project, cwd: Optional[Path] = None) -> None:
    path = _bm_dir(cwd) / PROJECT_FILE
    _write_json(path, project.model_dump())


def load_project(cwd: Optional[Path] = None) -> Optional[Project]:
    path = _bm_dir(cwd) / PROJECT_FILE
    if not path.exists():
        return None
    data = _read_json(path)
    return Project(**data)


# ── Tasks ────────────────────────────────────────────────────────────────────

def save_tasks(tasks: list[Task], cwd: Optional[Path] = None) -> None:
    path = _bm_dir(cwd) / TASKS_FILE
    _write_json(path, [t.model_dump() for t in tasks])


def load_tasks(cwd: Optional[Path] = None) -> list[Task]:
    path = _bm_dir(cwd) / TASKS_FILE
    if not path.exists():
        return []
    data = _read_json(path)
    return [Task(**t) for t in data]


def update_task(task: Task, cwd: Optional[Path] = None) -> None:
    """Update a single task in tasks.json by its id."""
    tasks = load_tasks(cwd)
    tasks = [task if t.id == task.id else t for t in tasks]
    save_tasks(tasks, cwd)


# ── Decisions ────────────────────────────────────────────────────────────────

def save_decisions(decisions: list[Decision], cwd: Optional[Path] = None) -> None:
    path = _bm_dir(cwd) / DECISIONS_FILE
    _write_json(path, [d.model_dump() for d in decisions])


def load_decisions(cwd: Optional[Path] = None) -> list[Decision]:
    path = _bm_dir(cwd) / DECISIONS_FILE
    if not path.exists():
        return []
    data = _read_json(path)
    return [Decision(**d) for d in data]


def append_decision(decision: Decision, cwd: Optional[Path] = None) -> None:
    decisions = load_decisions(cwd)
    decisions.append(decision)
    save_decisions(decisions, cwd)


# ── Gates ────────────────────────────────────────────────────────────────────

def save_gates(gates: list[Gate], cwd: Optional[Path] = None) -> None:
    path = _bm_dir(cwd) / GATES_FILE
    _write_json(path, [g.model_dump() for g in gates])


def load_gates(cwd: Optional[Path] = None) -> list[Gate]:
    path = _bm_dir(cwd) / GATES_FILE
    if not path.exists():
        return []
    data = _read_json(path)
    return [Gate(**g) for g in data]


def update_gate(gate: Gate, cwd: Optional[Path] = None) -> None:
    gates = load_gates(cwd)
    gates = [gate if g.id == gate.id else g for g in gates]
    save_gates(gates, cwd)


# ── Spec ─────────────────────────────────────────────────────────────────────

def load_spec(cwd: Optional[Path] = None) -> dict:
    """Load accumulated project spec (key-value pairs from decisions)."""
    path = _bm_dir(cwd) / SPEC_FILE
    return _read_json(path) if path.exists() else {}


def save_spec(spec: dict, cwd: Optional[Path] = None) -> None:
    path = _bm_dir(cwd) / SPEC_FILE
    _write_json(path, spec)


def update_spec(key: str, value, cwd: Optional[Path] = None) -> None:
    """Add or update a single key in the spec."""
    spec = load_spec(cwd)
    spec[key] = value
    save_spec(spec, cwd)


# ── Task outputs ─────────────────────────────────────────────────────────────

def save_task_output(task_id: str, output: dict, cwd: Optional[Path] = None) -> None:
    outputs_dir = _bm_dir(cwd) / OUTPUTS_DIR
    outputs_dir.mkdir(parents=True, exist_ok=True)
    path = outputs_dir / f"{task_id}_output.json"
    _write_json(path, output)


def load_task_output(task_id: str, cwd: Optional[Path] = None) -> Optional[dict]:
    path = _bm_dir(cwd) / OUTPUTS_DIR / f"{task_id}_output.json"
    if not path.exists():
        return None
    return _read_json(path)


# ── Graph ────────────────────────────────────────────────────────────────────

def save_graph(graph: dict, cwd: Optional[Path] = None) -> None:
    path = _bm_dir(cwd) / GRAPH_FILE
    _write_json(path, graph)


def load_graph(cwd: Optional[Path] = None) -> dict:
    path = _bm_dir(cwd) / GRAPH_FILE
    return _read_json(path) if path.exists() else {"nodes": [], "edges": []}


# ── Init helper ──────────────────────────────────────────────────────────────

def initialize_storage(cwd: Optional[Path] = None) -> Path:
    """Create the .buildmind/ directory and all required subdirectories."""
    bm = _bm_dir(cwd)
    bm.mkdir(parents=True, exist_ok=True)
    (bm / OUTPUTS_DIR).mkdir(exist_ok=True)
    return bm
