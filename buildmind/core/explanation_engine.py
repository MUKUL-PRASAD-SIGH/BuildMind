"""
Explanation Engine -- Phase 8 core service.

Converts AI-generated code and system components into plain-English explanations.
"""
import json
import re
from typing import Dict, Any, List
from pathlib import Path

from buildmind.config.settings import BuildMindConfig
from buildmind.llm.client import LLMClient
from buildmind.models.project import Project
from buildmind.models.task import Task
from buildmind.prompts.loader import load
from buildmind.core.file_writer import FileAction

def _extract_json(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text

class ExplanationEngine:
    def __init__(self, config: BuildMindConfig):
        self.config = config
        self.llm = LLMClient(config)

    def generate_component_explanation(self, project: Project, task: Task, file_actions: List[FileAction], spec: dict, use_mock: bool = False) -> Dict[str, Any]:
        """
        Explain the implementation of an AI executed task.
        """
        if use_mock:
            return {
                "component_name": task.title,
                "what_it_does": "Mock implementation placeholder.",
                "why_it_matters": "Demonstrates functionality without using API.",
                "how_it_works": ["Step 1: Mocked", "Step 2: Completed"],
                "code_summary": "Simple test structures.",
                "watch_out_for": ["This is mock data"],
                "connection_to_goal": "Proves the UI pipelines work.",
            }

        system_prompt = load("explainer_system")
        
        # Build giant text dump of code
        code_output = ""
        for fa in file_actions:
            code_output += f"--- {fa.path} ---\n{fa.content}\n\n"

        user_prompt = load(
            "explainer_user",
            intent=project.intent,
            task_title=task.title,
            code_output=code_output[:3000],  # Truncate to save tokens during explanation phase
            spec_json=json.dumps(spec, indent=2)
        )

        raw = self.llm.complete_sync(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=self.config.models.explainer,
            max_tokens=1000,
            temperature=0.3,
            json_mode=True,
        )
        
        raw_clean = _extract_json(raw)
        
        try:
            return json.loads(raw_clean)
        except Exception as e:
            raise ValueError(f"Explainer: Failed to parse LLM response.\nError: {e}")
