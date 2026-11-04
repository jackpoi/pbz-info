"""带重试的只读文件读取。

游戏可能在应用读取的同一瞬间写存档，因此失败要视为"正在写入"而不是"文件损坏"。
"""

from __future__ import annotations

import time
from pathlib import Path

DEFAULT_DELAYS = (0.1, 0.3, 0.9)


class ReadError(Exception):
    pass


def read_bytes(path: Path, delays: tuple[float, ...] = DEFAULT_DELAYS) -> bytes:
    path = Path(path)
    last: Exception | None = None
    for attempt in range(len(delays)):
        try:
            with path.open("rb") as fh:
                return fh.read()
        except FileNotFoundError as exc:
            raise ReadError(f"文件不存在：{path}") from exc
        except OSError as exc:
            last = exc
            time.sleep(delays[attempt])
    raise ReadError(f"读取失败：{path}（{last}）")


def stat_signature(path: Path) -> tuple[int, int] | None:
    """(mtime_ns, size)。用于判断是否需要重新解析。"""
    try:
        st = Path(path).stat()
    except OSError:
        return None
    return st.st_mtime_ns, st.st_size
