"""
Prompt template loader for BuildMind.
Loads .txt files from buildmind/prompts/ and interpolates variables.

Uses string.Template (${var} syntax) which is safe against curly braces
in the template body (unlike str.format()).
"""
from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Any

PROMPTS_DIR = Path(__file__).parent


def load(template_name: str, **variables: Any) -> str:
    """
    Load a prompt template and interpolate variables.

    Template variables use ${var_name} syntax (string.Template style).
    Curly braces in the template body (e.g. JSON examples) are safe.

    Args:
        template_name: filename without .txt extension (e.g. 'decomposer_system')
        **variables: key=value pairs to substitute

    Example:
        load("decomposer_user", project_id="proj_abc", intent="Build a REST API")
    """
    path = PROMPTS_DIR / f"{template_name}.txt"
    if not path.exists():
        available = [p.stem for p in PROMPTS_DIR.glob("*.txt") if p.stem != "__init__"]
        raise FileNotFoundError(
            f"Prompt template not found: {path}\n"
            f"Available: {available}"
        )
    template_text = path.read_text(encoding="utf-8")
    try:
        return Template(template_text).substitute(**variables)
    except KeyError as e:
        raise KeyError(
            f"Prompt template '{template_name}' requires variable {e}. "
            f"Provided: {list(variables.keys())}"
        ) from e


def list_templates() -> list[str]:
    """Return all available prompt template names."""
    return sorted(p.stem for p in PROMPTS_DIR.glob("*.txt"))
