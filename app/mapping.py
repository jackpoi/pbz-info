"""Boss / 难度名称映射表。

内置表随包发布（data/bosses.json），用户可在 %LOCALAPPDATA%\\pbz-info\\bosses.override.json
里用同样的结构覆盖或补充，不必等新版本。
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        candidate = Path(bundle) / "data"
        if candidate.is_dir():
            return candidate
    return repo_root() / "data"


@dataclass
class Mapping:
    difficulties: dict[str, str] = field(default_factory=dict)
    names: dict[str, str] = field(default_factory=dict)
    english: dict[str, str] = field(default_factory=dict)

    def boss_name(self, boss_id: str) -> str | None:
        return self.names.get(boss_id)

    def difficulty_name(self, raw: int | str) -> str | None:
        return self.difficulties.get(str(raw))

    def is_known(self, boss_id: str) -> bool:
        return boss_id in self.names


def _read(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load(override: Path | None = None) -> Mapping:
    base = _read(data_dir() / "bosses.json")
    mapping = Mapping(
        difficulties=dict(base.get("difficulties") or {}),
        names={},
        english={},
    )
    for boss_id, entry in (base.get("bosses") or {}).items():
        if isinstance(entry, dict):
            if entry.get("zh"):
                mapping.names[boss_id] = entry["zh"]
            if entry.get("en"):
                mapping.english[boss_id] = entry["en"]

    if override is not None:
        extra = _read(Path(override))
        mapping.difficulties.update(extra.get("difficulties") or {})
        for boss_id, entry in (extra.get("bosses") or {}).items():
            if not isinstance(entry, dict):
                continue
            if entry.get("zh"):
                mapping.names[boss_id] = entry["zh"]
            if entry.get("en"):
                mapping.english[boss_id] = entry["en"]

    return mapping
