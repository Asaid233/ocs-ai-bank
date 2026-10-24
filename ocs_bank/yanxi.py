# -*- coding: utf-8 -*-
"""言溪题库客户端。

接口与 OCS 的 AnswererWrapper 一致：
POST https://tk.enncy.cn/query
{"token": "...", "title": "...", "options": "...", "type": "...", "v": "2", ...}

返回：
- 命中：{"code":1,"data":{"question":"...","answer":"...","times":97,"ai":false}}
- 未收录：{"code":0,"data":{"answer":"非常抱歉，题库没有该题的答案…"},"message":"请求失败"}
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any

from .config import load_config


class YanxiError(RuntimeError):
    """言溪请求失败，message 可直接展示。"""


def _post(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (OCS-Bank/1.0)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise YanxiError("言溪题库 Token 无效或无权限，请到设置里检查") from exc
        if exc.code == 429:
            raise YanxiError("言溪题库请求过于频繁（429），请稍后重试") from exc
        raise YanxiError(f"言溪题库请求失败（HTTP {exc.code}）") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, socket.timeout):
            raise YanxiError(f"言溪题库请求超时（{timeout}s）") from exc
        raise YanxiError(f"无法连接言溪题库：{reason}") from exc
    except socket.timeout as exc:
        raise YanxiError(f"言溪题库请求超时（{timeout}s）") from exc

    try:
        parsed = json.loads(body)
    except ValueError as exc:
        raise YanxiError(f"言溪题库返回了非 JSON 内容：{body[:120]}") from exc
    if not isinstance(parsed, dict):
        raise YanxiError("言溪题库返回格式异常")
    return parsed


def query(title: str, options: str, qtype: str) -> dict[str, Any] | None:
    """查询言溪题库；未收录返回 None，请求失败抛 YanxiError。"""
    cfg = load_config()
    token = (cfg.get("yanxi_token") or "").strip()
    if not token:
        raise YanxiError("尚未配置言溪题库 Token")
    url = (cfg.get("yanxi_url") or "https://tk.enncy.cn/query").strip()
    timeout = int(cfg.get("yanxi_timeout") or 15)

    response = _post(
        url,
        {
            "token": token,
            "title": title,
            "options": options,
            "type": qtype,
            "images": [],
            "v": "2",
            "suggestion_title": "",
            "suggestion_options": "",
        },
        timeout,
    )

    if str(response.get("code")) == "0":
        return None

    data = response.get("data")
    if not isinstance(data, dict):
        return None
    answer = data.get("answer")
    if isinstance(answer, (list, tuple)):
        answer = "#".join(str(item) for item in answer)
    answer = str(answer or "").strip()
    if not answer or "题库没有该题的答案" in answer:
        return None

    return {
        "answer": answer,
        "ai": bool(data.get("ai")),
        "times": int(data.get("times") or 0),
        "matched_question": str(data.get("question") or ""),
    }
