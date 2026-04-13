"""
Pydantic models for BuildMind tasks.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    HUMAN_REQUIRED = "HUMAN_REQUIRED"
    AI_EXECUTABLE = "AI_EXECUTABLE"
    UNCLASSIFIED = "UNCLASSIFIED"


class TaskSubType(str, Enum):
    """Finer-grained task category — drives model routing."""
    CODE_PYTHON = "code_python"
    CODE_JS = "code_js"
    CODE_TS = "code_ts"
    CODE_SQL = "code_sql"
    CODE_SHELL = "code_shell"
    CODE_GENERIC = "code_generic"
    DOCUMENTATION = "documentation"
    ARCHITECTURE = "architecture"
    DECISION_TECH = "decision_tech"       # technology choice
    DECISION_DESIGN = "decision_design"   # UX / API design
    DECISION_POLICY = "decision_policy"   # security, compliance
    DECISION_THRESHOLD = "decision_threshold"  # numeric/parameter values
    UNKNOWN = "unknown"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    AWAITING_HUMAN = "AWAITING_HUMAN"
    APPROVED = "APPROVED"           # human decided, ready to execute
    EXECUTING = "EXECUTING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class TaskComplexity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Task(BaseModel):
    """A single atomic unit of work within a project."""
    id: str                                             # e.g. "t1", "t2"
    project_id: str
    title: str
    description: str
    type: TaskType = TaskType.UNCLASSIFIED
    sub_type: TaskSubType = TaskSubType.UNKNOWN
    status: TaskStatus = TaskStatus.PENDING
    complexity: Optional[TaskComplexity] = None
    dependencies: list[str] = Field(default_factory=list)   # task IDs
    blocks: list[str] = Field(default_factory=list)          # task IDs this blocks
    classification_reason: Optional[str] = None              # why HUMAN or AI
    assigned_model: Optional[str] = None                     # which model ran it
    output_file: Optional[str] = None                        # path to generated file
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def is_human(self) -> bool:
        return self.type == TaskType.HUMAN_REQUIRED

    @property
    def is_ai(self) -> bool:
        return self.type == TaskType.AI_EXECUTABLE

    @property
    def is_done(self) -> bool:
        return self.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED, TaskStatus.APPROVED)

    @property
    def is_blocked(self) -> bool:
        return self.status == TaskStatus.AWAITING_HUMAN

    def can_execute(self, completed_task_ids: set[str]) -> bool:
        """Returns True if all dependencies are satisfied."""
        return all(dep in completed_task_ids for dep in self.dependencies)
