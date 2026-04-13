"""
Export Engine -- Phase 9 core service.

Generates comprehensive Markdown project summaries and exports specs without LLM bloat.
"""
from typing import List
from pathlib import Path

from buildmind.config.settings import BuildMindConfig
from buildmind.models.project import Project
from buildmind.models.task import Task
from buildmind.models.decision import Decision
from buildmind.storage.project_store import load_spec

class ExportEngine:
    def __init__(self, config: BuildMindConfig):
        self.config = config
        
    def export_summary(self, project: Project, tasks: List[Task], decisions: List[Decision], output_path: Path) -> Path:
        """
        Creates a markdown summary deterministically parsing state.
        """
        spec = load_spec()
        
        lines = []
        lines.append(f"# Project Summary: {project.title}")
        lines.append("\n## Intent")
        lines.append(f"> {project.intent}")
        
        if project.context.stack or project.context.constraints:
            lines.append("\n## Context")
            if project.context.stack:
                lines.append(f"- **Stack**: {project.context.stack}")
            if project.context.constraints:
                lines.append(f"- **Constraints**: {project.context.constraints}")
                
        lines.append("\n## Architectural Decisions (Project Spec)")
        if spec:
            for k, v in spec.items():
                # Make spec keys human readable
                formatted_key = k.replace('_', ' ').title()
                lines.append(f"- **{formatted_key}**: {v}")
        else:
            lines.append("No decisions recorded yet.")
            
        lines.append("\n## Task Breakdown & Implementation Plan")
        for t in tasks:
            status_emoji = "✅" if t.is_done else "⏳"
            task_type = "🧠 Human Decision" if t.is_human else "🤖 AI Execution"
            lines.append(f"### {status_emoji} {t.id}: {t.title} ({task_type})")
            lines.append(f"{t.description}")
            if t.classification_reason:
                lines.append(f"\n*Why {task_type}:* {t.classification_reason}")
            lines.append("")
            
        lines.append("\n## Detailed Human Decisions Log")
        for d in decisions:
            accepted = "*(AI Suggestion accepted)*" if d.accepted_ai_suggestion else "*(Custom/Manual choice)*"
            lines.append(f"### Task {d.task_id}: {d.chosen_value}")
            lines.append(f"Chosen option: {accepted}")
            if d.custom_input:
                lines.append(f"Custom Input: {d.custom_input}")
            if d.skip_reason:
                lines.append(f"Skipped Reason: {d.skip_reason}")
            lines.append("")
            
        content = "\n".join(lines)
        output_path.write_text(content, encoding="utf-8")
        return output_path
