"""Screen configuration models and YAML load/save utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

log = get_logger("conflu.screener.configs")

# Resolve screens_dir relative to the project root (4 levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _resolve_screens_dir() -> Path:
    """Resolve screens_dir to an absolute path.

    If configured as a relative path, resolve it from the project root
    so it works regardless of the current working directory.
    """
    raw = Path(settings.screen.screens_dir)
    if raw.is_absolute():
        return raw
    return (_PROJECT_ROOT / raw).resolve()


class UniverseConfig(BaseModel):
    """Universe configuration for screen."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    markets: list[str] = Field(default_factory=lambda: ["america"])
    index: str | None = None


class FilterRule(BaseModel):
    """A single filter rule in a screen configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: str
    indicator: str
    params: dict[str, Any] = Field(default_factory=dict)
    operator: Literal["gt", "lt", "eq", "crosses_above", "crosses_below"] = "gt"
    timeframe: str = "1D"
    negate: bool = False
    compare_timeframe: str | None = None


class ScreenConfig(BaseModel):
    """A complete screen configuration loaded from YAML."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str = ""
    asset_classes: list[str] = Field(default_factory=lambda: ["equities", "crypto"])
    timeframes: list[str] = Field(default_factory=lambda: ["1D", "4h"])
    filters: list[FilterRule] = Field(default_factory=list)
    universe: UniverseConfig = Field(default_factory=UniverseConfig)
    limit: int = Field(default=500, ge=1, le=2000)

    @field_validator("filters")
    @classmethod
    def validate_filter_names(cls, filters: list[FilterRule]) -> list[FilterRule]:
        """Ensure all referenced filter names are registered in the TV filter map."""
        # Lazy import to avoid circular dependency with tv_specialist
        from backend.app.infrastructure.screener.tv_specialist import FILTER_MAP

        for flt in filters:
            if flt.indicator not in FILTER_MAP:
                msg = (
                    f"Unknown filter '{flt.indicator}'. "
                    f"Available: {list(FILTER_MAP.keys())}"
                )
                raise ValueError(msg)
        return filters


def load_screen_template(name: str) -> ScreenConfig:
    """Load a screen configuration from YAML.

    Args:
        name: Screen name (filename without .yaml extension).

    Returns:
        ScreenConfig instance.

    Raises:
        FileNotFoundError: If template file doesn't exist.
        ValueError: If YAML validation fails.
    """
    screens_dir = _resolve_screens_dir()
    path = screens_dir / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Screen template '{name}' not found at {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return ScreenConfig(**data)


def list_screen_templates() -> list[dict[str, str]]:
    """List available screen configuration names with descriptions.

    Returns:
        List of dicts with 'name' and 'description' keys.
    """
    screens_dir = _resolve_screens_dir()
    templates: list[dict[str, str]] = []
    for p in sorted(screens_dir.glob("*.yaml")):
        try:
            cfg = load_screen_template(p.stem)
            templates.append({"name": cfg.name, "description": cfg.description})
        except Exception:
            log.warning("failed_to_load_template", template=str(p))
            templates.append({"name": p.stem, "description": ""})
    return templates


def save_screen_config(config: ScreenConfig, path: str | Path | None = None) -> Path:
    """Save a screen configuration to YAML.

    Args:
        config: ScreenConfig instance.
        path: Optional output path. Defaults to config/screens/{name}.yaml.

    Returns:
        Path to the saved file.
    """
    if path is None:
        screens_dir = _resolve_screens_dir()
        screens_dir.mkdir(parents=True, exist_ok=True)
        path = screens_dir / f"{config.name}.yaml"

    data = config.model_dump(mode="python")
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    log.info("screen_config_saved", name=config.name, path=str(path))
    return Path(path)
