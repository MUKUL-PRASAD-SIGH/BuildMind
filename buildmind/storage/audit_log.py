"""
Append-only audit log — records every action BuildMind takes.
Stored as JSONL (one JSON object per line) in .buildmind/audit_log.jsonl
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from buildmind.config.settings import get_buildmind_dir

AUDIT_LOG_FILE = "audit_log.jsonl"


def _log_path(cwd: Optional[Path] = None) -> Path:
    return get_buildmind_dir(cwd) / AUDIT_LOG_FILE


def log_event(
    event_type: str,
    project_id: str,
    data: dict[str, Any],
    task_id: Optional[str] = None,
    user_action: bool = False,
    cwd: Optional[Path] = None,
) -> None:
    """Append a single event to the audit log."""
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type,
        "project_id": project_id,
        "task_id": task_id,
        "user_action": user_action,
        "data": data,
    }
    path = _log_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def read_log(cwd: Optional[Path] = None) -> list[dict]:
    """Read all audit log entries."""
    path = _log_path(cwd)
    if not path.exists():
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


# ── Typed event helpers ──────────────────────────────────────────────────────

def log_project_created(project_id: str, intent: str, cwd: Optional[Path] = None) -> None:
    log_event("PROJECT_CREATED", project_id, {"intent": intent}, cwd=cwd)


def log_tasks_decomposed(project_id: str, task_count: int, cwd: Optional[Path] = None) -> None:
    log_event("TASKS_DECOMPOSED", project_id, {"task_count": task_count}, cwd=cwd)


def log_task_classified(project_id: str, task_id: str, task_type: str, reason: str, cwd: Optional[Path] = None) -> None:
    log_event("TASK_CLASSIFIED", project_id, {"type": task_type, "reason": reason}, task_id=task_id, cwd=cwd)


def log_gate_presented(project_id: str, task_id: str, options_count: int, cwd: Optional[Path] = None) -> None:
    log_event("GATE_PRESENTED", project_id, {"options_count": options_count}, task_id=task_id, cwd=cwd)


def log_gate_approved(project_id: str, task_id: str, chosen_value: str, accepted_ai: bool, cwd: Optional[Path] = None) -> None:
    log_event("GATE_APPROVED", project_id,
              {"chosen_value": chosen_value, "accepted_ai_suggestion": accepted_ai},
              task_id=task_id, user_action=True, cwd=cwd)


def log_gate_skipped(project_id: str, task_id: str, reason: str, cwd: Optional[Path] = None) -> None:
    log_event("GATE_SKIPPED", project_id, {"reason": reason}, task_id=task_id, user_action=True, cwd=cwd)


def log_task_started(project_id: str, task_id: str, model: str, cwd: Optional[Path] = None) -> None:
    log_event("TASK_STARTED", project_id, {"model": model}, task_id=task_id, cwd=cwd)


def log_task_completed(project_id: str, task_id: str, output_file: Optional[str], cwd: Optional[Path] = None) -> None:
    log_event("TASK_COMPLETED", project_id, {"output_file": output_file}, task_id=task_id, cwd=cwd)


def log_task_failed(project_id: str, task_id: str, error: str, attempt: int, cwd: Optional[Path] = None) -> None:
    log_event("TASK_FAILED", project_id, {"error": error, "attempt": attempt}, task_id=task_id, cwd=cwd)


def log_validation_result(project_id: str, task_id: str, passed: bool, violations: list, cwd: Optional[Path] = None) -> None:
    log_event("VALIDATION_RESULT", project_id,
              {"passed": passed, "violations": violations}, task_id=task_id, cwd=cwd)
