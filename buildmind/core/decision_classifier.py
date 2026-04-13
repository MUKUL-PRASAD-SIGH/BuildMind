"""
Decision Classifier — Phase 3 core service.

Classifies each task as HUMAN_REQUIRED or AI_EXECUTABLE.
Runs after Task Decomposer, updates task objects in storage.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from buildmind.config.settings import BuildMindConfig
from buildmind.llm.client import LLMClient
from buildmind.models.project import Project
from buildmind.models.task import Task, TaskType, TaskSubType, TaskStatus
from buildmind.prompts.loader import load
from buildmind.storage.project_store import save_tasks, update_task
from buildmind.storage.audit_log import log_task_classified


def _extract_json(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


def _apply_classifications(
    tasks: list[Task],
    raw_json: str,
    project_id: str,
) -> list[Task]:
    """Merge classification results into task objects."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Classifier: LLM returned invalid JSON.\n"
            f"Error: {e}\n"
            f"Raw (first 300):\n{raw_json[:300]}"
        )

    classifications = data.get("classifications", [])
    id_to_classification = {c["task_id"]: c for c in classifications}
    id_to_task = {t.id: t for t in tasks}

    for task in tasks:
        classification = id_to_classification.get(task.id)
        if not classification:
            # Default to HUMAN if classifier missed it
            task.type = TaskType.HUMAN_REQUIRED
            task.classification_reason = "Defaulted to HUMAN (classifier did not return result)"
            continue

        raw_type = classification.get("type", "HUMAN_REQUIRED")
        try:
            task.type = TaskType(raw_type)
        except ValueError:
            task.type = TaskType.HUMAN_REQUIRED

        # Sub-type (only for AI tasks)
        raw_sub = classification.get("sub_type")
        if task.type == TaskType.AI_EXECUTABLE and raw_sub:
            try:
                task.sub_type = TaskSubType(raw_sub)
            except ValueError:
                task.sub_type = TaskSubType.CODE_GENERIC

        task.classification_reason = classification.get("reason", "")

        # Update status based on type
        if task.type == TaskType.HUMAN_REQUIRED:
            task.status = TaskStatus.AWAITING_HUMAN
        else:
            # Will be unlocked when dependencies are met
            task.status = TaskStatus.PENDING

        log_task_classified(
            project_id, task.id,
            task.type.value,
            task.classification_reason or ""
        )

    return tasks


class DecisionClassifier:
    """
    Classifies tasks as HUMAN_REQUIRED or AI_EXECUTABLE.
    Runs as a batch: sends all tasks in one LLM call.
    Uses claude-haiku (cheap + fast).
    """

    def __init__(self, config: BuildMindConfig):
        self.config = config
        self.llm = LLMClient(config)

    def classify(self, project: Project, tasks: list[Task]) -> list[Task]:
        """
        Classify all tasks. Updates task objects in-place and saves to storage.
        """
        tasks_for_prompt = [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "complexity": t.complexity.value if t.complexity else "medium",
                "dependencies": t.dependencies,
            }
            for t in tasks
        ]

        system_prompt = load("classifier_system")
        user_prompt   = load(
            "classifier_user",
            project_id=project.id,
            intent=project.intent,
            tasks_json=json.dumps(tasks_for_prompt, indent=2),
        )

        raw = self.llm.complete_sync(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=self.config.models.classifier,
            max_tokens=2048,
            temperature=0.1,
            json_mode=True,
        )

        raw_clean = _extract_json(raw)
        tasks = _apply_classifications(tasks, raw_clean, project.id)

        save_tasks(tasks)
        return tasks
