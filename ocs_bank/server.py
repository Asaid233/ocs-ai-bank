# -*- coding: utf-8 -*-
"""HTTP 服务：OCS 题库接口 + 管理后台静态页面。"""
from __future__ import annotations

import json
import mimetypes
import re
import sys
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__, db
from .config import WEB_DIR, load_config, public_config, save_config
from .question import (
    make_key,
    normalize_answer,
    normalize_type,
    options_to_text,
    parse_options,
)
from .service import answer_question, test_answer

STARTED_AT = time.time()
_BANK_ID_RE = re.compile(r"^/api/bank/(\d+)$")

# 不依赖 Windows 注册表的 MIME 映射，避免 .js 被当成 text/plain 导致浏览器拒绝执行
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


def _log(message: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


class Handler(BaseHTTPRequestHandler):
    server_version = f"OCSBank/{__version__}"
    protocol_version = "HTTP/1.1"

    # ---------------- 基础响应 ----------------
    def _cors(self) -> None:
        # 只有题库查询接口需要对任意网课页面开放跨域；
        # 管理接口（题库、配置、统计）仅允许同源访问，避免其他网站读取本地数据。
        if urlparse(self.path).path != "/api/search":
            return
        origin = self.headers.get("Origin")
        self.send_header("Access-Control-Allow-Origin", origin or "*")
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def _send(self, status: int, body: bytes, content_type: str, extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        if extra:
            for key, value in extra.items():
                self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8", {"Cache-Control": "no-store"})

    def _error(self, message: str, status: int = 400) -> None:
        self._json({"code": 0, "msg": message}, status=status)

    def handle_one_request(self) -> None:
        # 同一连接上的每个请求都必须重置 body 缓存，否则 PUT/POST 之后的
        # 请求会读到上一个请求的 body，未读完的字节还会污染 keep-alive 连接。
        self._body_cache = None
        super().handle_one_request()

    def _body(self) -> dict[str, Any]:
        cached = getattr(self, "_body_cache", None)
        if cached is not None:
            return cached
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            self._body_cache = {}
            return {}
        if length > 8 * 1024 * 1024:
            raise ValueError("请求体过大")
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError("请求体必须是合法 JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("请求体必须是 JSON 对象")
        self._body_cache = parsed
        return parsed

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        if self.path.startswith("/api/"):
            _log(f"{self.command} {self.path.split('?')[0]} -> {args[1] if len(args) > 1 else ''}")

    # ---------------- 路由 ----------------
    def do_OPTIONS(self) -> None:  # noqa: N802
        # 预检请求正常没有 body；若有，必须读掉，否则会污染 keep-alive 连接
        length = int(self.headers.get("Content-Length") or 0)
        if length > 0:
            self.rfile.read(length)
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self) -> None:  # noqa: N802
        # 允许监控工具探测页面，但不让 HEAD /api/search 触发 AI 调用
        if urlparse(self.path).path.startswith("/api/"):
            self.send_response(405)
            self.send_header("Allow", "GET, POST, OPTIONS")
            self.send_header("Content-Length", "0")
            self._cors()
            self.end_headers()
            return
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        try:
            self._route_get()
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._error(f"服务器异常：{exc}", 500)

    def do_POST(self) -> None:  # noqa: N802
        try:
            self._body()  # 先读完请求体，保持 keep-alive 连接干净
            self._route_post()
        except ValueError as exc:
            self._error(str(exc), 400)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._error(f"服务器异常：{exc}", 500)

    def do_PUT(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 0:
                self._body()
            path = urlparse(self.path).path
            match = _BANK_ID_RE.match(path)
            if not match:
                self._error("接口不存在", 404)
                return
            self._update_bank(int(match.group(1)))
        except ValueError as exc:
            self._error(str(exc), 400)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._error(f"服务器异常：{exc}", 500)

    def do_DELETE(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 0:
                self.rfile.read(length)
            path = urlparse(self.path).path
            match = _BANK_ID_RE.match(path)
            if not match:
                self._error("接口不存在", 404)
                return
            item_id = int(match.group(1))
            ok = db.delete_question(item_id)
            self._json({"code": 1 if ok else 0, "msg": "已删除" if ok else "题目不存在"})
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._error(f"服务器异常：{exc}", 500)

    # ---------------- GET ----------------
    def _route_get(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/api/health":
            cfg = load_config()
            self._json({
                "ok": True,
                "version": __version__,
                "uptime": int(time.time() - STARTED_AT),
                "bank": db.stats()["total_questions"],
                "ai_configured": bool((cfg.get("api_key") or "").strip()),
                "ai_enabled": cfg["ai_enabled"],
                "model": cfg["model"],
            })
            return

        if path == "/api/stats":
            data = db.stats()
            data["recent"] = db.recent_logs(10)
            data["version"] = __version__
            data["uptime"] = int(time.time() - STARTED_AT)
            data["config"] = public_config()
            self._json({"code": 1, "data": data})
            return

        if path == "/api/config":
            self._json({"code": 1, "data": public_config()})
            return

        if path == "/api/bank":
            keyword = (query.get("q") or [""])[0].strip()
            qtype = normalize_type((query.get("type") or [""])[0])
            source = (query.get("source") or [""])[0].strip()
            page = _int(query.get("page"), 1)
            page_size = _int(query.get("page_size"), 20)
            data = db.list_questions(keyword, qtype, source, page, page_size)
            self._json({"code": 1, "data": data})
            return

        if path == "/api/bank/export":
            fmt = (query.get("format") or ["json"])[0].lower()
            if fmt == "csv":
                body = db.export_csv()
                self._send(
                    200, body, "text/csv; charset=utf-8",
                    {"Content-Disposition": 'attachment; filename="ocs-bank.csv"', "Cache-Control": "no-store"},
                )
            else:
                items = db.all_questions()
                payload = [
                    {
                        "question": item["question"],
                        "options": item["options"],
                        "type": item["qtype"],
                        "answer": item["answer"],
                        "source": item["source"],
                        "confidence": item["confidence"],
                    }
                    for item in items
                ]
                body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
                self._send(
                    200, body, "application/json; charset=utf-8",
                    {"Content-Disposition": 'attachment; filename="ocs-bank.json"', "Cache-Control": "no-store"},
                )
            return

        if path == "/api/logs":
            self._json({"code": 1, "data": db.recent_logs(_int(query.get("limit"), 20))})
            return

        if path == "/api/search":
            result = answer_question(
                _first(query, "title", "question", "q", "text"),
                _first(query, "options"),
                _first(query, "type"),
            )
            self._json(result)
            return

        # 静态资源
        self._serve_static(path)

    # ---------------- POST ----------------
    def _route_post(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/search":
            body = self._body()
            result = answer_question(
                str(body.get("title") or body.get("question") or ""),
                body.get("options") or "",
                str(body.get("type") or ""),
            )
            self._json(result)
            return

        if path == "/api/test":
            body = self._body()
            result = test_answer(
                str(body.get("title") or body.get("question") or ""),
                body.get("options") or "",
                str(body.get("type") or ""),
            )
            self._json(result)
            return

        if path == "/api/ping":
            from .deepseek import AIError, ping

            try:
                data = ping()
            except AIError as exc:
                self._json({"code": 0, "msg": str(exc)})
                return
            self._json({"code": 1, "msg": "连接正常", "data": data})
            return

        if path == "/api/config":
            body = self._body()
            patch = {
                key: value
                for key, value in body.items()
                if key not in ("clear_key", "clear_yanxi_token")
            }
            if body.get("clear_key"):
                patch["api_key"] = ""
            if body.get("clear_yanxi_token"):
                patch["yanxi_token"] = ""
            save_config(patch)
            self._json({"code": 1, "msg": "已保存", "data": public_config()})
            return

        if path == "/api/bank/import":
            body = self._body()
            raw_items = body.get("items") if isinstance(body.get("items"), list) else body
            if not isinstance(raw_items, list):
                raise ValueError("导入内容必须是数组")
            items: list[dict[str, Any]] = []
            for entry in raw_items:
                if not isinstance(entry, dict):
                    continue
                question = str(entry.get("question") or entry.get("title") or "").strip()
                raw_answer = str(entry.get("answer") or "").strip()
                if not question or not raw_answer:
                    continue
                qtype = normalize_type(str(entry.get("type") or entry.get("qtype") or ""))
                options = options_to_text(parse_options(entry.get("options")))
                # 兼容旧题库里的字母答案 / 判断题 "对、错"，转成 OCS 最容易匹配的文本
                answer, _ = normalize_answer(raw_answer, qtype, parse_options(options))
                items.append({
                    "qkey": make_key(question),
                    "question": question,
                    "answer": answer or raw_answer,
                    "options": options,
                    "qtype": qtype,
                    "confidence": entry.get("confidence"),
                })
            if not items:
                raise ValueError("没有解析到有效题目（需要 question 与 answer 字段）")
            result = db.import_items(items)
            self._json({"code": 1, "msg": f"导入完成：新增 {result['inserted']}，更新 {result['updated']}，跳过 {result['skipped']}", "data": result})
            return

        if path == "/api/bank":
            body = self._body()
            question = str(body.get("question") or "").strip()
            answer = str(body.get("answer") or "").strip()
            if not question or not answer:
                raise ValueError("题目和答案不能为空")
            options = str(body.get("options") or "")
            qtype = normalize_type(str(body.get("type") or ""))
            qkey = make_key(question)
            if db.get_by_key(qkey):
                raise ValueError("题库中已存在相同题目")
            item_id = db.upsert_question(qkey, question, answer, options, qtype, "manual", 1.0)
            self._json({"code": 1, "msg": "已新增", "data": {"id": item_id}})
            return

        self._error("接口不存在", 404)

    # ---------------- 题库编辑 ----------------
    def _update_bank(self, item_id: int) -> None:
        item = db.get_by_id(item_id)
        if not item:
            self._error("题目不存在", 404)
            return
        body = self._body()
        patch: dict[str, Any] = {}
        if "answer" in body:
            answer = str(body.get("answer") or "").strip()
            if not answer:
                raise ValueError("答案不能为空")
            patch["answer"] = answer
            patch["confidence"] = 1.0
            patch["source"] = "manual"
        if "question" in body:
            question = str(body.get("question") or "").strip()
            if not question:
                raise ValueError("题目不能为空")
            patch["question"] = question
            patch["qkey"] = make_key(question)
            if patch["qkey"] != item["qkey"] and db.get_by_key(patch["qkey"]):
                self._error("题库中已存在相同题目", 409)
                return
        if "options" in body:
            patch["options"] = str(body.get("options") or "")
        if "type" in body:
            patch["qtype"] = normalize_type(str(body.get("type") or ""))
        ok = db.update_question(item_id, patch)
        self._json({"code": 1 if ok else 0, "msg": "已保存" if ok else "没有可保存的改动"})

    # ---------------- 静态文件 ----------------
    def _serve_static(self, path: str) -> None:
        if path in ("", "/"):
            path = "/index.html"
        relative = path.lstrip("/")
        target = (WEB_DIR / relative).resolve()
        try:
            target.relative_to(WEB_DIR.resolve())
        except ValueError:
            self._error("非法路径", 403)
            return
        if not target.is_file():
            self._error("页面不存在", 404)
            return
        content_type = STATIC_TYPES.get(target.suffix.lower())
        if not content_type:
            content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if content_type.startswith("text/"):
                content_type += "; charset=utf-8"
        body = target.read_bytes()
        self._send(200, body, content_type, {"Cache-Control": "no-cache"})


def _int(value: list[str] | None, default: int) -> int:
    if not value:
        return default
    try:
        return int(value[0])
    except (TypeError, ValueError):
        return default


def _first(query: dict[str, list[str]], *names: str) -> str:
    for name in names:
        if query.get(name):
            return query[name][0]
    return ""


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


def serve(port: int | None = None, host: str | None = None, open_browser: bool = True) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    db.init_db()
    cfg = load_config()
    bind_host = host or cfg.get("host") or "127.0.0.1"
    bind_port = int(port or cfg.get("port") or 8787)

    try:
        httpd = Server((bind_host, bind_port), Handler)
    except OSError as exc:
        print(f"\n[启动失败] 端口 {bind_port} 无法使用：{exc}")
        print(f"可能已被其他程序占用，换一个端口试试：python app.py --port {bind_port + 1}\n")
        raise SystemExit(1) from exc

    httpd.daemon_threads = True
    url = f"http://{'127.0.0.1' if bind_host in ('0.0.0.0', '::') else bind_host}:{bind_port}"
    key_ready = "已配置" if (cfg.get("api_key") or "").strip() else "未配置（请到设置里填写）"
    print("")
    print("  OCS 本地 AI 题库  v" + __version__)
    print("  ------------------------------------------")
    print(f"  管理后台   {url}")
    print(f"  题库接口   {url}/api/search")
    print(f"  题库数量   {db.stats()['total_questions']} 题")
    print(f"  DeepSeek   {key_ready} · {cfg['model']}")
    print("  Ctrl+C 停止服务")
    print("")

    if open_browser:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  服务已停止")
    finally:
        httpd.server_close()
