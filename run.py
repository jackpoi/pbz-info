"""开发启动器：双击或 `python run.py`。

这个 Python 发行版是精简版（python315._pth 控制 sys.path），
`python -m app.main` 不会把当前目录加进去，所以统一从这里进。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
