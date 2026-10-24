#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCS 本地 AI 题库 —— 启动入口。

用法:
    python app.py                # 默认 http://127.0.0.1:8787
    python app.py --port 9000
    python app.py --no-browser
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ocs_bank.server import serve  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="OCS 本地 AI 题库（DeepSeek）")
    parser.add_argument("--port", type=int, default=None, help="监听端口，默认 8787")
    parser.add_argument("--host", default=None, help="监听地址，默认 127.0.0.1")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器")
    args = parser.parse_args()
    serve(port=args.port, host=args.host, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
