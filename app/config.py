"""用户配置：%LOCALAPPDATA%\\pbz-info\\config.json

onefile 打包后 sys._MEIPASS 退出即删，所以窗口尺寸、存档路径这类东西必须落在外面。
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from . import logs

log = logs.get("config")

DEFAULTS: dict = {
    "schema": 1,
    "saveDir": None,
    "savePath": None,
    "exePath": None,
    "window": {"width": 1180, "height": 820, "x": None, "y": None},
    "view": {"sort": "idx", "dir": -1},
    # "info" 只记状态变化；改 "debug" 才会记每次轮询（日志增长快，仅排查时用）
    "log": {"level": "info"},
}


def default_path() -> Path:
    return default_dir() / "config.json"


def default_dir() -> Path:
    import sys

    base = Path.home() / "AppData" / "Local" if sys.platform == "win32" else Path.home() / ".local" / "share"
    return base / "pbz-info"


def load(path: Path | None = None) -> dict:
    path = Path(path) if path else default_path()
    config = copy.deepcopy(DEFAULTS)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return config
    except (OSError, ValueError) as exc:
        # 以前静默回落默认值，"设置莫名其妙全丢了"查不出来源
        log.warning("配置文件读不出来，改用默认值 · %s · %s", path, exc)
        return config
    if not isinstance(raw, dict):
        log.warning("配置文件不是对象，改用默认值 · %s", path)
        return config

    for key, default in DEFAULTS.items():
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(default, dict):
            if isinstance(value, dict):
                dropped = [k for k in value if k not in default]
                if dropped:
                    log.info("忽略配置里的未知字段 %s.%s", key, ", ".join(dropped))
                config[key].update({k: v for k, v in value.items() if k in default})
        else:
            config[key] = value
    return config


def save(config: dict, path: Path | None = None) -> None:
    path = Path(path) if path else default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
