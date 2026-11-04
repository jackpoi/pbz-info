"""生成一个假的桥接页面，用来目视检查错误状态（NEED_EXE / NO_GAME / stale）。

    python tools/make_state_preview.py NEED_EXE
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "web" / "dist" / "index.html"
OUT = ROOT / ".taste-skill"

FAKE = {
    "NEED_EXE": """
      window.pywebview = { api: {
        get_state: async () => ({
          ok: false,
          error: { code: 'NEED_EXE', message: '这个存档需要一个密钥。请选择游戏的 PBZ.exe（每台机器只需一次）。' },
          meta: {}, cycle: null, totals: null, bosses: []
        }),
        get_config: async () => ({}),
      }};""",
    "NO_GAME": """
      window.pywebview = { api: {
        get_state: async () => ({
          ok: false,
          error: { code: 'NO_GAME', message: '没有在 Steam 库里找到《影之刃零》' },
          meta: {}, cycle: null, totals: null, bosses: []
        }),
        get_config: async () => ({}),
      }};""",
    "STALE": """
      const good = %SAMPLE%;
      window.pywebview = { api: {
        get_state: async () => Object.assign({}, good, {
          ok: false, stale: true,
          error: { code: 'PARSE_FAIL', message: 'GCM 校验失败（密钥不对，或文件正在写入）' },
          meta: Object.assign({}, good.meta, { stale: true }),
        }),
        get_config: async () => ({}),
      }};""",
}


def main() -> int:
    kind = (sys.argv[1] if len(sys.argv) > 1 else "NEED_EXE").upper()
    if kind not in FAKE:
        print(f"可用的状态：{', '.join(FAKE)}")
        return 2

    html = DIST.read_text(encoding="utf-8")
    snippet = FAKE[kind]
    if "%SAMPLE%" in snippet:
        sample = (ROOT / "web" / "src" / "mock.js").read_text(encoding="utf-8")
        body = sample.split("export const MOCK =", 1)[1].strip().rstrip(";")
        snippet = snippet.replace("%SAMPLE%", body)

    html = html.replace("<body>", "<body>\n<script>" + snippet + "</script>\n", 1)
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"state-{kind.lower()}.html"
    target.write_text(html, encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
