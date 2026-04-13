"""
Task Decomposer — Phase 2 core service.

Takes user intent + context, calls LLM, returns a list of Task objects.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from buildmind.config.settings import BuildMindConfig
from buildmind.llm.client import LLMClient
from buildmind.models.project import Project
from buildmind.models.task import Task, TaskStatus, TaskType, TaskSubType, TaskComplexity
from buildmind.prompts.loader import load
from buildmind.storage.project_store import save_tasks
from buildmind.storage.audit_log import log_tasks_decomposed


def _extract_json(text: str) -> str:
    """Strip markdown code fences if LLM wraps JSON in them."""
    # Remove ```json ... ``` or ``` ... ```
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


def _parse_task_list(raw_json: str, project: Project) -> list[Task]:
    """Parse raw JSON from LLM into Task objects."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Task Decomposer: LLM returned invalid JSON.\n"
            f"Error: {e}\n"
            f"Raw response (first 500 chars):\n{raw_json[:500]}"
        )

    raw_tasks = data.get("tasks", [])
    if not raw_tasks:
        raise ValueError("Task Decomposer: LLM returned an empty task list.")

    tasks: list[Task] = []
    for raw in raw_tasks:
        complexity_str = raw.get("estimated_complexity", "medium")
        try:
            complexity = TaskComplexity(complexity_str)
        except ValueError:
            complexity = TaskComplexity.MEDIUM

        task = Task(
            id=raw.get("id", f"t{len(tasks)+1}"),
            project_id=project.id,
            title=raw.get("title", "Untitled task"),
            description=raw.get("description", ""),
            type=TaskType.UNCLASSIFIED,
            sub_type=TaskSubType.UNKNOWN,
            status=TaskStatus.PENDING,
            complexity=complexity,
            dependencies=raw.get("dependencies", []),
        )
        tasks.append(task)

    # Build reverse `blocks` map
    id_to_task = {t.id: t for t in tasks}
    for task in tasks:
        for dep_id in task.dependencies:
            if dep_id in id_to_task:
                id_to_task[dep_id].blocks.append(task.id)

    return tasks


class TaskDecomposer:
    """
    Breaks user intent into a list of atomic Task objects.
    Calls the LLM once per project start.
    """

    def __init__(self, config: BuildMindConfig):
        self.config = config
        self.llm = LLMClient(config)

    def decompose(self, project: Project) -> list[Task]:
        """
        Synchronous entry point for CLI.
        Calls LLM, parses response, saves tasks, returns list.
        """
        # Build context string
        ctx_parts = []
        if project.context.stack:
            ctx_parts.append(f"Tech stack: {project.context.stack}")
        if project.context.environment:
            ctx_parts.append(f"Environment: {project.context.environment}")
        if project.context.constraints:
            ctx_parts.append(f"Constraints: {project.context.constraints}")
        context_str = "\n".join(ctx_parts) if ctx_parts else "Not specified"

        system_prompt = load("decomposer_system")
        user_prompt   = load(
            "decomposer_user",
            project_id=project.id,
            intent=project.intent,
            context=context_str,
            mode=project.mode.value,
        )

        raw = self.llm.complete_sync(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=self.config.models.decomposer,
            max_tokens=4096,
            temperature=0.2,
            json_mode=True,
        )

        raw_clean = _extract_json(raw)
        tasks = _parse_task_list(raw_clean, project)

        # Persist
        save_tasks(tasks)
        log_tasks_decomposed(project.id, len(tasks))

        return tasks
