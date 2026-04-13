"""
Execution Engine -- Phase 5 core service.

For each AI_EXECUTABLE task that is PENDING and unblocked:
  1. Calls LLM with full context + spec + task details
  2. Parses JSON response into FileAction objects
  3. Writes files locally
"""
from __future__ import annotations

import json
import re
from typing import List

from buildmind.config.settings import BuildMindConfig
from buildmind.llm.client import LLMClient
from buildmind.models.project import Project
from buildmind.models.task import Task, TaskStatus
from buildmind.prompts.loader import load
from buildmind.storage.project_store import load_spec
from buildmind.core.file_writer import FileAction

def _extract_json(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text

class Executor:
    def __init__(self, config: BuildMindConfig):
        self.config = config
        self.llm = LLMClient(config)

    def get_ready_tasks(self, tasks: list[Task]) -> list[Task]:
        """Return AI tasks that are PENDING and have no blocking incomplete dependencies."""
        completed = {t.id for t in tasks if t.is_done}
        return [
            t for t in tasks
            if t.is_ai and t.status.value == "PENDING" and t.can_execute(completed)
        ]

    def execute_task(self, project: Project, task: Task, use_mock: bool = False) -> List[FileAction]:
        """Execute a single AI task and return a list of file actions."""
        if use_mock:
            return self._mock_execute(project, task)

        spec = load_spec()
        context_str = ""
        if project.context.stack:
            context_str += f"Stack: {project.context.stack}\n"
        if project.context.constraints:
            context_str += f"Constraints: {project.context.constraints}\n"

        system_prompt = load("executor_system")
        user_prompt = load(
            "executor_user",
            project_id=project.id,
            intent=project.intent,
            context=context_str or "Not specified",
            spec_json=json.dumps(spec, indent=2) if spec else "{}",
            task_id=task.id,
            task_title=task.title,
            task_description=task.description,
        )

        raw = self.llm.complete_sync(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=self.config.models.executor,
            max_tokens=4000,
            temperature=0.1,
            json_mode=True,
        )
        
        raw_clean = _extract_json(raw)
        
        try:
            data = json.loads(raw_clean)
            files_data = data.get("files", [])
            return [FileAction(**f) for f in files_data]
        except Exception as e:
            raise ValueError(
                f"Executor: Failed to parse LLM response for {task.id}.\n"
                f"Error: {e}\nRaw response snippet: {raw_clean[:200]}"
            )

    def _mock_execute(self, project: Project, task: Task) -> List[FileAction]:
        """Generate test files without calling LLM."""
        safe_title = task.title.lower().replace(" ", "_").replace("/", "_")
        mock_file = FileAction(
            path=f"src/{safe_title}.txt",
            content=f"# Mock implementation for task: {task.title}\n# Description: {task.description}\n",
            action="create",
            description=f"Mock logic for {task.id}"
        )
        return [mock_file]
