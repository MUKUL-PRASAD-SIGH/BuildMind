"""
BuildMind configuration — loads from .buildmind/config.yaml
No API keys required. All model access goes through the IDE's AI.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

# ── Default config written on `buildmind init` ──────────────────────────────

DEFAULT_CONFIG: dict = {
    "version": "1",
    "project_name": None,  # filled after init

    # Models — uses your IDE's available models (no API keys needed)
    "models": {
        "decomposer":    "claude-opus",      # Deep reasoning — task decomposition
        "classifier":    "claude-haiku",     # Fast — classify HUMAN vs AI
        "decision_card": "claude-sonnet",    # Balanced — generate decision cards
        "executor":      "claude-sonnet",    # Code generation
        "validator":     "claude-haiku",     # Quick spec checks
        "explainer":     "claude-sonnet",    # Explanation generation
        "graph_update":  "claude-haiku",     # Graph node label updates
    },

    # Fallback chain — if a model is unavailable, try the next
    "fallback_chain": [
        "claude-sonnet",
        "claude-haiku",
        "gemini-pro",
        "gemini-flash",
    ],

    # IDE integration — auto-detected
    "ide_integration": {
        "type": "antigravity",  # auto-detected from env
    },

    # Output settings
    "output": {
        "code_dir": "src",                  # where AI writes code files
        "config_dir": "config",             # where config files are written
        "overwrite_existing": False,        # ask before overwriting files
        "write_comments": True,             # generate commented code
    },

    # Decision settings
    "decisions": {
        "require_acknowledgment": True,     # gate must be interacted with
        "show_ai_suggestion": True,
        "allow_custom_input": True,
        "min_options": 3,                   # minimum options to show per decision
    },

    # Mode — default flow
    "mode": "build",    # Options: "build", "learn", "audit"
}


# ── Settings model ───────────────────────────────────────────────────────────

class ModelSettings(BaseModel):
    decomposer:    str = "claude-opus"
    classifier:    str = "claude-haiku"
    decision_card: str = "claude-sonnet"
    executor:      str = "claude-sonnet"
    validator:     str = "claude-haiku"
    explainer:     str = "claude-sonnet"
    graph_update:  str = "claude-haiku"


class OutputSettings(BaseModel):
    code_dir:           str  = "src"
    config_dir:         str  = "config"
    overwrite_existing: bool = False
    write_comments:     bool = True


class DecisionSettings(BaseModel):
    require_acknowledgment: bool = True
    show_ai_suggestion:     bool = True
    allow_custom_input:     bool = True
    min_options:            int  = 3


class BuildMindConfig(BaseModel):
    version:        str = "1"
    project_name:   Optional[str] = None
    models:         ModelSettings = Field(default_factory=ModelSettings)
    fallback_chain: list[str] = Field(default_factory=lambda: [
        "claude-sonnet", "claude-haiku", "gemini-pro"
    ])
    output:         OutputSettings = Field(default_factory=OutputSettings)
    decisions:      DecisionSettings = Field(default_factory=DecisionSettings)
    mode:           str = "build"


# ── Loader ───────────────────────────────────────────────────────────────────

BUILDMIND_DIR = ".buildmind"
CONFIG_FILE   = "config.yaml"


def get_buildmind_dir(cwd: Optional[Path] = None) -> Path:
    """Returns the .buildmind/ directory path."""
    return (cwd or Path.cwd()) / BUILDMIND_DIR


def config_path(cwd: Optional[Path] = None) -> Path:
    return get_buildmind_dir(cwd) / CONFIG_FILE


def load_config(cwd: Optional[Path] = None) -> BuildMindConfig:
    """Load config from .buildmind/config.yaml. Returns defaults if not found."""
    path = config_path(cwd)
    if not path.exists():
        return BuildMindConfig()
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return BuildMindConfig(**raw)


def save_config(config: BuildMindConfig, cwd: Optional[Path] = None) -> None:
    """Write config to .buildmind/config.yaml."""
    path = config_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False, sort_keys=False)


def write_default_config(project_name: str, cwd: Optional[Path] = None) -> BuildMindConfig:
    """Write the default config for a new project."""
    cfg = DEFAULT_CONFIG.copy()
    cfg["project_name"] = project_name
    config = BuildMindConfig(**cfg)
    save_config(config, cwd)
    return config


def is_initialized(cwd: Optional[Path] = None) -> bool:
    """Check if the current directory has been initialized as a BuildMind project."""
    return config_path(cwd).exists()
