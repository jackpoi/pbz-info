"""开发用：把当前存档归一化后的视图打印成 JSON。

    python tools/dump.py                 # 自动发现
    python tools/dump.py --save-dir "..." # 指定存档目录
    python tools/dump.py --compact        # 单行输出
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.service import Service  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-dir", type=Path, default=None)
    ap.add_argument("--compact", action="store_true")
    args = ap.parse_args()

    view = Service().refresh(save_dir=args.save_dir, force=True)
    if args.compact:
        print(json.dumps(view, ensure_ascii=False))
    else:
        print(json.dumps(view, ensure_ascii=False, indent=2))

    return 0 if view.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
