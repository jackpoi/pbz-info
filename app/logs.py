"""日志：%LOCALAPPDATA%\\pbz-info\\logs\\pbz-info.log

留日志只为了一件事：出问题时能查。所以这里记录的是"状态变化和错误"，
不是"每次轮询都写一行"——界面每秒调一次 get_state()，全记下来只会把日志冲成噪声。

写不进去也不能影响程序：所有初始化都吞掉自己的异常，最坏情况退化成只在
控制台输出（开发时）或什么都不记（打包后没有 stderr）。
"""

from __future__ import annotations

import faulthandler
import logging
import logging.handlers
import sys
import threading
from pathlib import Path

FILENAME = "pbz-info.log"
CRASH_FILENAME = "crash.log"

#: 单文件 2 MB × 4 份 = 上限 8 MB，够放下十几次故障现场
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 3

FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-5s %(name)-10s %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"

_logger = logging.getLogger("app")
# 没调用 configure 时（测试、库用法）不要冒出 lastResort 的 stderr 警告
_logger.addHandler(logging.NullHandler())
_configured = False
_level = logging.INFO
_log_dir: Path | None = None
_log_path: Path | None = None
_crash_stream = None


class _ShortName(logging.Formatter):
    """`app.service` → `service`：日志里只看模块名，省掉一列的宽度。"""

    def format(self, record: logging.LogRecord) -> str:
        if record.name.startswith("app."):
            record.name = record.name[4:]
        return super().format(record)


def default_dir() -> Path:
    from . import config as config_mod

    return config_mod.default_dir() / "logs"


def configure(
    log_dir: Path | str | None = None,
    level: str = "info",
    *,
    max_bytes: int = MAX_BYTES,
    backup_count: int = BACKUP_COUNT,
) -> Path | None:
    """安装文件日志。幂等：重复调用只更新级别，不会重复挂 handler。

    返回日志文件路径；目录不可写时返回 None（程序照常运行）。
    """
    global _configured, _log_dir, _log_path, _crash_stream

    _set_level(level)
    if _configured:
        return _log_path

    directory = Path(log_dir) if log_dir else default_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            directory / FILENAME,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
    except OSError:
        _attach_console()
        _install_hooks(None)
        _configured = True
        return None

    handler.setFormatter(_ShortName(FORMAT, DATEFMT))
    _logger.addHandler(handler)
    _logger.setLevel(_level)
    _logger.propagate = False

    _log_dir = directory
    _log_path = directory / FILENAME
    _attach_console()

    # 原生崩溃（ctypes 里的解码器、栈溢出）走不了 Python 异常，
    # faulthandler 至少能把当时的 Python 栈写下来。
    try:
        _crash_stream = (directory / CRASH_FILENAME).open("a", encoding="utf-8", errors="replace")
        faulthandler.enable(file=_crash_stream, all_threads=True)
    except OSError:
        _crash_stream = None

    _install_hooks(directory)
    _configured = True
    return _log_path


def _attach_console() -> None:
    """打包后 stderr 是 None，只有开发时才有终端可看。"""
    if sys.stderr is None:
        return
    if any(isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stderr
           for h in _logger.handlers):
        return
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(_ShortName(FORMAT, DATEFMT))
    _logger.addHandler(console)


def _install_hooks(directory: Path | None) -> None:
    log = logging.getLogger("app.crash")

    def on_uncaught(exc_type, exc, tb) -> None:
        log.critical("未捕获的异常", exc_info=(exc_type, exc, tb))

    def on_thread(args) -> None:
        if args.exc_type is SystemExit:
            return
        name = args.thread.name if args.thread is not None else "?"
        log.critical(
            "线程 %s 里未捕获的异常", name, exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
        )

    def on_unraisable(args) -> None:
        log.error("析构/回调里的异常：%s", args.err_msg or args.object, exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = on_uncaught
    threading.excepthook = on_thread
    if hasattr(sys, "unraisablehook"):
        sys.unraisablehook = on_unraisable


def _set_level(level: str) -> None:
    global _level
    _level = logging.DEBUG if str(level).lower() in {"debug", "verbose", "trace"} else logging.INFO
    _logger.setLevel(_level)


def set_level(level: str) -> None:
    _set_level(level)


def level() -> int:
    return _level


def log_dir() -> Path:
    return _log_dir or default_dir()


def log_path() -> Path | None:
    return _log_path


def get(name: str) -> logging.Logger:
    return logging.getLogger(f"app.{name}")


def shutdown() -> None:
    """测试用：卸掉 handler，避免用例之间互相写同一个文件。"""
    global _configured, _log_dir, _log_path, _crash_stream

    for handler in list(_logger.handlers):
        if handler.__class__.__name__ == "NullHandler":
            continue
        _logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:  # noqa: BLE001
            pass
    if _crash_stream is not None:
        try:
            faulthandler.disable()
            _crash_stream.close()
        except Exception:  # noqa: BLE001
            pass
    _crash_stream = None
    _log_dir = None
    _log_path = None
    _configured = False
