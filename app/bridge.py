"""前端唯一入口：pywebview 的 js_api。

JS 侧每 1 秒调一次 get_state()；Python 只在文件变化时重新解析。
所有方法都必须返回可 JSON 序列化的值，异常一律转成 {ok: false, error}。
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

from . import __version__
from . import config as config_mod
from . import discovery, logs, service as service_mod
from . import update as update_mod

log = logs.get("bridge")


def _open_url(url: str) -> bool:
    """用系统默认浏览器打开外链。file:// 页面里 window.open 不可靠，统一走这里。"""
    if sys.platform != "win32":
        return False
    try:
        os.startfile(url)  # noqa: S606 - 参数是我们自己写死的 https 地址
    except OSError:
        return False
    return True


class Bridge:
    def __init__(
        self,
        svc: service_mod.Service,
        config: dict,
        *,
        config_path: Path | None = None,
        window=None,
    ) -> None:
        self._service = svc
        self._config = config
        self._config_path = config_path or config_mod.default_path()
        self._window = window
        self._lock = threading.Lock()
        self._save_dir = Path(config["saveDir"]) if config.get("saveDir") else None
        self._save_path = Path(config["savePath"]) if config.get("savePath") else None

    # ------------------------------------------------------------------ 数据

    def get_state(self, force: bool = False) -> dict:
        if not log.isEnabledFor(10):  # DEBUG 没开时不做计时，省掉每秒两次 clock 调用
            with self._lock:
                return self._service.refresh(
                    save_dir=self._save_dir,
                    save_path=self._save_path,
                    force=bool(force),
                )
        started = time.monotonic()
        with self._lock:
            state = self._service.refresh(
                save_dir=self._save_dir,
                save_path=self._save_path,
                force=bool(force),
            )
        log.debug("get_state(force=%s) · %d 个 Boss · %.1f ms", force, len(state.get("bosses") or []), (time.monotonic() - started) * 1000)
        return state

    def refresh(self) -> dict:
        return self.get_state(True)

    # ------------------------------------------------------------------ 存档

    def pick_save_file(self) -> dict:
        picked = self._dialog(
            "open",
            file_types=("存档文件 (*.sav)", "所有文件 (*.*)"),
        )
        if not picked:
            return {"canceled": True}
        return self._apply_save_path(Path(picked))

    def pick_save_folder(self) -> dict:
        picked = self._dialog("folder")
        if not picked:
            return {"canceled": True}
        return self._apply_save_dir(service_mod.resolve_save_dir(picked))

    def set_save_dir(self, path: str) -> dict:
        target = Path(path)
        if target.is_file():
            return self._apply_save_path(target)
        return self._apply_save_dir(service_mod.resolve_save_dir(target))

    def _apply_save_path(self, path: Path) -> dict:
        """用户明确选了一个 .sav：就读这个文件，不替换成同目录的主存档。"""
        if not path.is_file():
            log.warning("切换存档失败：文件不存在 %s", path)
            return {
                "ok": False,
                "error": {"code": service_mod.ERROR_BAD_DIR, "message": f"文件不存在：{path}"},
            }
        log.info("切换到文件 %s", path)
        with self._lock:
            self._save_path = path
            self._save_dir = path.parent
            self._config["savePath"] = str(path)
            self._config["saveDir"] = str(path.parent)
            self._persist()
            return self._service.refresh(save_path=self._save_path, force=True)

    def _apply_save_dir(self, directory: Path) -> dict:
        main = directory / service_mod.MAIN_SAVE
        if not main.is_file():
            log.warning("切换存档失败：%s 里没有 %s", directory, service_mod.MAIN_SAVE)
            return {
                "ok": False,
                "error": {
                    "code": service_mod.ERROR_BAD_DIR,
                    "message": f"{directory} 里没有 {service_mod.MAIN_SAVE}",
                },
            }
        log.info("切换到目录 %s", directory)
        with self._lock:
            self._save_dir = directory
            self._save_path = None
            self._config["saveDir"] = str(directory)
            self._config["savePath"] = None
            self._persist()
            return self._service.refresh(save_dir=self._save_dir, force=True)

    # -------------------------------------------------------------------- 密钥

    def pick_exe(self) -> dict:
        picked = self._dialog(
            "open",
            file_types=("游戏主程序 (PBZ.exe)", "可执行文件 (*.exe)"),
        )
        if not picked:
            return {"canceled": True}
        return self.set_exe(picked)

    def set_exe(self, path: str) -> dict:
        exe = Path(path)
        if not exe.is_file():
            log.warning("指定 PBZ.exe 失败：文件不存在 %s", path)
            return {"ok": False, "error": {"code": service_mod.ERROR_NEED_EXE, "message": "文件不存在"}}
        log.info("指定 PBZ.exe · %s", exe)
        with self._lock:
            self._service.set_exe(exe)
            self._config["exePath"] = str(exe)
            self._persist()
            return self._service.refresh(save_dir=self._save_dir, force=True)

    # -------------------------------------------------------------------- 其它

    def list_accounts(self) -> list:
        try:
            _install, _exe, accounts = discovery.discover()
        except discovery.DiscoveryError:
            return []
        current = str(self._save_dir) if self._save_dir else None
        return [
            {
                "steamId": a.steam_id,
                "saveDir": str(a.save_dir),
                "hasSave": a.has_main,
                "current": current is not None and os.path.normcase(str(a.save_dir)) == os.path.normcase(current),
            }
            for a in accounts
        ]

    def select_account(self, steam_id: str) -> dict:
        for account in self.list_accounts():
            if account["steamId"] == steam_id:
                return self._apply_save_dir(Path(account["saveDir"]))
        return {"ok": False, "error": {"code": service_mod.ERROR_BAD_DIR, "message": "账号不存在"}}

    def use_main_save(self) -> dict:
        """从"指定的某个文件"回到该存档目录下的主存档。

        选的是 1RealTime 里的快照时，向上找到真正放着 PBZSaveGame.sav 的那一层。
        注意：不能持锁再调 _apply_save_dir，那里面还要拿同一把锁（会死锁）。
        """
        with self._lock:
            directory = self._save_dir
        if directory is None:
            return {"ok": False}

        for candidate in (directory, *list(directory.parents)[:2]):
            if (candidate / service_mod.MAIN_SAVE).is_file():
                return self._apply_save_dir(candidate)

        return {
            "ok": False,
            "error": {
                "code": service_mod.ERROR_BAD_DIR,
                "message": f"{directory} 附近没有 {service_mod.MAIN_SAVE}",
            },
        }

    def open_save_dir(self) -> dict:
        target = self._save_dir
        if target is None:
            state = self.get_state()
            save_path = (state.get("meta") or {}).get("savePath")
            target = Path(save_path).parent if save_path else None
        if target is None or not target.is_dir():
            return {"ok": False}
        if sys.platform == "win32":
            os.startfile(str(target))  # noqa: S606
        return {"ok": True}

    def open_log_dir(self) -> dict:
        """关于弹窗里的「打开日志目录」。目录不存在时先建出来。"""
        target = logs.log_dir()
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError:
            log.warning("日志目录不可用：%s", target, exc_info=True)
            return {"ok": False}
        if sys.platform == "win32":
            os.startfile(str(target))  # noqa: S606
        return {"ok": True, "path": str(target)}

    def log_frontend(self, level: str, message: str) -> dict:
        """前端错误回传：白屏、未捕获的 Promise、Vue 渲染错误都从这里进日志。"""
        text = str(message)[:2000]
        name = level if level in {"debug", "info", "warning", "error"} else "warning"
        getattr(log, name)("前端 · %s", text)
        return {"ok": True}

    def get_config(self) -> dict:
        return dict(self._config)

    # -------------------------------------------------------------------- 版本

    def get_version(self) -> dict:
        return {
            "version": __version__,
            "repo": update_mod.REPO,
            "releasesPage": update_mod.RELEASES_PAGE,
        }

    def check_update(self) -> dict:
        """只有用户点“检查更新”才会走到这里；启动时不调用。"""
        try:
            return update_mod.check()
        except Exception as exc:  # noqa: BLE001 - 检查更新绝不把界面打崩
            return {
                "ok": False,
                "current": __version__,
                "error": {"code": "UNEXPECTED", "message": f"{type(exc).__name__}: {exc}"},
            }

    def open_url(self, url: str) -> dict:
        """只允许打开发布页 / 仓库地址这类 https 外链，不接受任意输入。"""
        if not isinstance(url, str) or not url.startswith("https://github.com/jackpoi/pbz-info"):
            return {"ok": False, "error": {"code": "BAD_URL", "message": "只支持项目自己的 GitHub 地址"}}
        return {"ok": _open_url(url)}

    def set_view(self, sort: str, direction: int) -> dict:
        self._config.setdefault("view", {})
        self._config["view"] = {"sort": sort, "dir": int(direction)}
        self._persist()
        return {"ok": True}

    def quit(self) -> dict:
        if self._window is not None:
            self._window.destroy()
        return {"ok": True}

    # -------------------------------------------------------------------- 内部

    def _dialog(self, kind: str, file_types: tuple[str, ...] = ()) -> str | None:
        if self._window is None:
            return None
        import webview

        dialog_type = {"open": webview.OPEN_DIALOG, "folder": webview.FOLDER_DIALOG}[kind]
        start_dir = str(self._save_dir) if self._save_dir and self._save_dir.is_dir() else ""
        result = self._window.create_file_dialog(
            dialog_type,
            directory=start_dir,
            allow_multiple=False,
            file_types=file_types,
        )
        if not result:
            return None
        return result[0] if isinstance(result, (list, tuple)) else result

    def attach_window(self, window) -> None:
        self._window = window

    def _persist(self) -> None:
        try:
            config_mod.save(self._config, self._config_path)
        except OSError:
            # 以前这里是静默 pass，"窗口尺寸/存档路径记不住"完全无从查起
            log.warning("配置写不进去：%s", self._config_path, exc_info=True)
