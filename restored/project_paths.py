"""Side-effect-free adaptation of owner's All Star project_paths.py.

Never mkdir/chdir/read raw_logs or write while importing or resolving paths.
Callers choose the root and explicitly authorize any later filesystem changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import os


@dataclass(frozen=True)
class ProjectPaths:
    project_root: Path
    base_dir: Path
    raw_logs: Path
    model_zoo: Path
    wormhole: Path
    templates: Path

    def safe_inside(self, approved_root: Path) -> bool:
        """Check all resolved paths stay inside an explicitly approved root."""
        root = approved_root.expanduser().resolve()
        for path in (self.project_root, self.base_dir, self.raw_logs,
                     self.model_zoo, self.wormhole, self.templates):
            candidate = path.expanduser().resolve()
            if candidate != root and root not in candidate.parents:
                return False
        return True


def resolve_paths(project_root: Path, env: Mapping[str, str] | None = None) -> ProjectPaths:
    values = os.environ if env is None else env
    root = Path(project_root).expanduser().resolve()
    base = Path(values.get("JANUS_BASE_DIR") or root).expanduser().resolve()
    raw = Path(values.get("JANUS_RAW_LOGS_DIR") or base / "raw_logs").expanduser().resolve()
    zoo = Path(values.get("JANUS_MODEL_ZOO_DIR") or base / "Model_Zoo").expanduser().resolve()
    wormhole = Path(values.get("JANUS_WORMHOLE_DIR") or base / "wormhole").expanduser().resolve()
    templates = Path(values.get("JANUS_TEMPLATES_DIR") or root / "templates").expanduser().resolve()
    return ProjectPaths(root, base, raw, zoo, wormhole, templates)
