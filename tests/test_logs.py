"""日志：默认目录、轮转上限、幂等、钩子。

日志本身不能成为新的故障源，所以这里重点测"写不进去也不影响程序"和
"不会无限增长"。
"""

from __future__ import annotations

import logging
import threading

import pytest

from app import logs


@pytest.fixture(autouse=True)
def _clean():
    logs.shutdown()
    yield
    logs.shutdown()


def _lines(path):
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_configure_writes_to_the_expected_directory(tmp_path):
    path = logs.configure(tmp_path / "logs")
    assert path == tmp_path / "logs" / "pbz-info.log"

    logs.get("service").info("已解析 · 12 个 Boss")
    for handler in logging.getLogger("app").handlers:
        handler.flush()

    text = path.read_text(encoding="utf-8")
    assert "已解析 · 12 个 Boss" in text
    # 模块名去掉了 app. 前缀，单行、可读
    assert " service " in text or text.split("INFO")[1].strip().startswith("service")


def test_default_directory_is_under_localappdata():
    path = logs.default_dir()
    assert path.name == "logs"
    assert path.parent.name == "pbz-info"


def test_configure_is_idempotent(tmp_path):
    first = logs.configure(tmp_path / "logs")
    second = logs.configure(tmp_path / "logs")
    assert first == second
    assert len(logging.getLogger("app").handlers) == len(
        [h for h in logging.getLogger("app").handlers]
    )
    # 重复调用不会再挂第二个文件 handler（否则每行都写两遍）
    files = [h for h in logging.getLogger("app").handlers if isinstance(h, logging.FileHandler)]
    assert len(files) == 1


def test_log_rotates_instead_of_growing_forever(tmp_path):
    logs.configure(tmp_path / "logs", max_bytes=400, backup_count=2)
    log = logs.get("service")
    for i in range(200):
        log.info("第 %d 行，长度凑一点凑一点凑一点", i)
    for handler in logging.getLogger("app").handlers:
        handler.flush()

    folder = tmp_path / "logs"
    files = sorted(p.name for p in folder.iterdir() if p.name.startswith("pbz-info.log"))
    assert "pbz-info.log" in files
    assert len(files) <= 3  # 当前文件 + 2 份轮转
    assert (folder / "pbz-info.log").stat().st_size <= 400 * 3


def test_unwritable_directory_does_not_raise(tmp_path):
    blocker = tmp_path / "logs"
    blocker.write_text("我不是目录", encoding="utf-8")  # mkdir 会失败
    assert logs.configure(blocker) is None
    logs.get("service").info("照常记，只是没地方落盘")


def test_level_can_be_switched(tmp_path):
    logs.configure(tmp_path / "logs", level="info")
    assert logs.level() == logging.INFO
    logs.set_level("debug")
    assert logs.level() == logging.DEBUG
    logs.set_level("info")
    assert logs.level() == logging.INFO


def test_thread_exception_is_recorded(tmp_path):
    path = logs.configure(tmp_path / "logs")

    def boom():
        raise RuntimeError("js_api 线程炸了")

    thread = threading.Thread(target=boom, name="pywebview-api")
    thread.start()
    thread.join()
    for handler in logging.getLogger("app").handlers:
        handler.flush()

    text = path.read_text(encoding="utf-8")
    assert "pywebview-api" in text
    assert "js_api 线程炸了" in text


def test_frontend_errors_are_written_to_the_same_file(tmp_path):
    path = logs.configure(tmp_path / "logs")
    import app.bridge as bridge_module

    bridge = bridge_module.Bridge.__new__(bridge_module.Bridge)  # 只需要 log_frontend
    bridge.log_frontend("error", "window.onerror · boom")
    for handler in logging.getLogger("app").handlers:
        handler.flush()
    assert "window.onerror · boom" in path.read_text(encoding="utf-8")


def test_crash_file_is_created(tmp_path):
    logs.configure(tmp_path / "logs")
    assert (tmp_path / "logs" / "crash.log").exists()
