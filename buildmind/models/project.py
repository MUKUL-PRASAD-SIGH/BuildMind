"""
Pydantic models for BuildMind projects.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class ProjectMode(str, Enum):
    BUILD = "build"
    LEARN = "learn"
    AUDIT = "audit"


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProjectContext(BaseModel):
    """Optional context the user provides about their project."""
    stack: Optional[str] = None          # e.g. "Python + FastAPI"
    environment: Optional[str] = None    # e.g. "Railway deployment"
    constraints: Optional[str] = None    # e.g. "must use PostgreSQL"
    existing_code: Optional[str] = None  # path to existing code context


class Project(BaseModel):
    """Top-level project record stored in .buildmind/project.json"""
    id: str                                         # e.g. "proj_abc123"
    title: str                                      # auto-derived from intent
    intent: str                                     # original user input
    context: ProjectContext = Field(default_factory=ProjectContext)
    mode: ProjectMode = ProjectMode.BUILD
    status: ProjectStatus = ProjectStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    project_dir: str = "."                          # absolute path to user's project

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()

    @classmethod
    def from_intent(cls, intent: str, project_dir: Path, context: Optional[ProjectContext] = None) -> "Project":
        """Create a new project from a user intent string."""
        import hashlib, time
        short_hash = hashlib.md5(f"{intent}{time.time()}".encode()).hexdigest()[:8]
        title = intent[:60] + ("..." if len(intent) > 60 else "")
        return cls(
            id=f"proj_{short_hash}",
            title=title,
            intent=intent,
            context=context or ProjectContext(),
            project_dir=str(project_dir.resolve()),
        )
