"""
Pydantic models for decisions and compulsion gates.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class DecisionOption(BaseModel):
    """A single numbered option in a decision card."""
    id: str                          # e.g. "opt_1"
    number: int                      # display number [1], [2], etc.
    label: str                       # Short label: "JWT (stateless)"
    what_it_is: str                  # One-liner explanation
    best_when: str                   # When to pick this
    weakness: str                    # Honest downside
    explain_detail: str              # Full text shown on `explain <num>`


class AISuggestion(BaseModel):
    """The AI's recommended choice with reasoning."""
    option_id: str
    option_number: int
    reasoning: str
    caveats: list[str] = Field(default_factory=list)
    confidence: str = "medium"       # "low", "medium", "high"


class DecisionCard(BaseModel):
    """Complete card shown to user for a HUMAN_REQUIRED task."""
    task_id: str
    why_human: str                                # Why AI can't decide this
    impact_areas: list[str] = Field(default_factory=list)
    options: list[DecisionOption]
    ai_suggestion: Optional[AISuggestion] = None
    blocks_tasks: list[str] = Field(default_factory=list)


class GateStatus(str, Enum):
    PENDING = "PENDING"
    AWAITING_HUMAN = "AWAITING_HUMAN"
    APPROVED = "APPROVED"
    SKIPPED = "SKIPPED"


class Gate(BaseModel):
    """Compulsion gate — blocks downstream tasks until human responds."""
    id: str
    project_id: str
    task_id: str
    status: GateStatus = GateStatus.PENDING
    blocks_tasks: list[str] = Field(default_factory=list)
    decision_card: Optional[DecisionCard] = None
    presented_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class Decision(BaseModel):
    """The human's recorded response to a decision card."""
    id: str
    project_id: str
    task_id: str
    gate_id: str

    # What was shown
    options_shown: list[DecisionOption]
    ai_suggestion: Optional[AISuggestion] = None

    # What was chosen
    chosen_option_id: Optional[str] = None
    chosen_option_number: Optional[int] = None
    chosen_value: str                           # Final resolved value/label
    custom_input: Optional[str] = None          # If user typed 'custom'
    accepted_ai_suggestion: bool = False
    skip_reason: Optional[str] = None           # If gate was skipped

    # Metadata
    mode: str = "manual"                        # "guided", "manual", "custom"
    decided_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_skipped(self) -> bool:
        return self.skip_reason is not None
