# -*- coding: utf-8 -*-
"""DeepSeek（OpenAI 兼容接口）调用与提示词。"""
from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.request
from typing import Any

from .config import load_config
from .question import type_label


class AIError(RuntimeError):
    """调用 AI 失败，message 可直接展示给用户。"""


SYSTEM_PROMPT = """你是中国高校网课平台的资深答题专家，长期负责慕课、学习通、智慧树、知到等平台的习题作答。
你的目标是给出与官方答案一致的结果，而不是解释知识。请严格依据题干和给出的选项推理。"""


def _build_user_prompt(question: str, options: str, qtype: str) -> str:
    label = type_label(qtype) if qtype else "未知题型"
    option_block = options.strip() if options.strip() else "（无选项）"
    if qtype == "completion":
        format_hint = '{"answer": ["第一空答案", "第二空答案"], "confidence": 0.95, "reason": "不超过30字"}'
        extra = "4. 填空题按空的顺序给出最简洁的标准答案，多个空放入数组，不要写序号，不要解释。\n"
    elif qtype == "judgement":
        format_hint = '{"answer": ["正确"], "confidence": 0.95, "reason": "不超过30字"}'
        extra = '4. 判断题答案只能是 "正确" 或 "错误"。\n'
    elif qtype == "multiple":
        format_hint = '{"answer": ["A", "C"], "confidence": 0.95, "reason": "不超过30字"}'
        extra = (
            "4. 这是多选题，返回全部正确项字母，不要漏选；选项顺序可能被打乱，按内容判断。\n"
            "5. 如果只有一个正确项，也只返回那一个，不要凑数。\n"
        )
    else:
        format_hint = '{"answer": ["A"], "confidence": 0.95, "reason": "不超过30字"}'
        extra = (
            "4. 这是单选题，只返回一个选项字母；选项顺序可能被打乱，按内容判断。\n"
            "5. 如果两个选项都像正确答案，选更符合题意的那一个，并适当降低 confidence。\n"
        )

    return f"""请作答下面的题目。

【题型】{label}
【题目】
{question.strip()}

【选项】
{option_block}

答题要求：
1. 只依据题目和选项作答，不要编造题目中不存在的信息。
2. 多选题宁缺毋滥，只选有把握的正确项；单选题必须给出唯一答案。
3. 如果题目信息不足、选项缺失或无法判断，把 confidence 设为 0.2 以下，不要硬猜。
{extra}最后，只输出 JSON，不要 Markdown 代码块，不要任何额外文字。

JSON 格式：
{format_hint}"""


def _endpoint(base_url: str) -> str:
    base = (base_url or "https://api.deepseek.com").strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _post(url: str, payload: dict[str, Any], api_key: str, timeout: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "OCS-Bank/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
        raise AIError(_http_error_message(exc.code, detail)) from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, socket.timeout):
            raise AIError(f"连接 DeepSeek 超时（{timeout}s），请检查网络或调大超时时间") from exc
        raise AIError(f"无法连接 DeepSeek：{reason}。请检查网络、代理或 base_url 配置") from exc
    except socket.timeout as exc:
        raise AIError(f"连接 DeepSeek 超时（{timeout}s）") from exc

    try:
        parsed = json.loads(body)
    except ValueError as exc:
        raise AIError(f"DeepSeek 返回了非 JSON 内容：{body[:160]}") from exc
    if not isinstance(parsed, dict):
        raise AIError("DeepSeek 返回格式异常")
    if parsed.get("error"):
        error = parsed["error"]
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise AIError(f"DeepSeek 返回错误：{message}")
    return parsed


def _http_error_message(status: int, detail: str) -> str:
    short = detail.strip().replace("\n", " ")[:200]
    mapping = {
        400: "请求格式错误（400）",
        401: "DeepSeek API Key 无效或已过期（401），请在「设置」里重新填写",
        402: "DeepSeek 账户余额不足（402），请充值后再试",
        403: "没有权限访问该模型（403），请检查模型名称",
        404: "接口地址不存在（404），请检查 base_url",
        422: "请求参数不合法（422）",
        429: "请求过于频繁或额度用尽（429），请稍后重试",
        500: "DeepSeek 服务内部错误（500），请稍后重试",
        502: "DeepSeek 网关错误（502），请稍后重试",
        503: "DeepSeek 服务繁忙（503），请稍后重试",
        504: "DeepSeek 响应超时（504），请稍后重试",
    }
    base = mapping.get(status, f"DeepSeek 请求失败（HTTP {status}）")
    if short and status not in (401, 402):
        base += f"：{short}"
    return base


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except ValueError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except ValueError:
            pass
    raise AIError(f"模型没有返回可解析的 JSON：{text[:160]}")


def ask(
    question: str,
    options: str,
    qtype: str,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """调用 DeepSeek 作答。

    返回 {answer: list[str], confidence: float, reason: str, tokens: int, model: str}
    """
    cfg = load_config()
    api_key = (cfg.get("api_key") or "").strip()
    if not api_key:
        raise AIError("还没有配置 DeepSeek API Key，请打开「设置」填写后重试")
    if not cfg.get("ai_enabled", True) and not force:
        raise AIError("AI 答题已在设置中关闭")

    model = cfg["model"]
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(question, options, qtype)},
        ],
        "max_tokens": cfg["max_tokens"],
        "stream": False,
    }
    is_reasoner = "reasoner" in model.lower()
    if not is_reasoner:
        payload["temperature"] = cfg["temperature"]
        payload["response_format"] = {"type": "json_object"}

    url = _endpoint(cfg["base_url"])
    timeout = int(cfg["timeout"])
    last_error: AIError | None = None

    for attempt in range(2):
        try:
            response = _post(url, payload, api_key, timeout)
            break
        except AIError as exc:
            last_error = exc
            message = str(exc)
            # 部分兼容接口不支持 response_format，去掉后重试一次
            if attempt == 0 and "response_format" in message:
                payload.pop("response_format", None)
                continue
            if attempt == 0 and ("429" in message or "503" in message or "502" in message or "500" in message):
                time.sleep(1.2)
                continue
            raise
    else:  # pragma: no cover
        raise last_error or AIError("DeepSeek 调用失败")

    choices = response.get("choices") or []
    if not choices:
        raise AIError("DeepSeek 没有返回任何答案")
    message = choices[0].get("message") or {}
    content = message.get("content") or ""
    if not content and message.get("reasoning_content"):
        content = message.get("reasoning_content") or ""

    data = _extract_json(content)
    raw_answer = data.get("answer")
    if raw_answer is None:
        raw_answer = data.get("answers", data.get("letters"))

    try:
        confidence = float(data.get("confidence", 0.6))
    except (TypeError, ValueError):
        confidence = 0.6
    confidence = max(0.0, min(1.0, confidence))

    usage = response.get("usage") or {}
    tokens = int(usage.get("total_tokens") or 0)

    return {
        "answer": raw_answer if isinstance(raw_answer, list) else [raw_answer] if raw_answer is not None else [],
        "confidence": confidence,
        "reason": str(data.get("reason") or "")[:200],
        "tokens": tokens,
        "model": model,
        "raw": content[:1000],
    }


def ping() -> dict[str, Any]:
    """设置页的连通性测试：发一个极短请求。"""
    cfg = load_config()
    api_key = (cfg.get("api_key") or "").strip()
    if not api_key:
        raise AIError("还没有配置 DeepSeek API Key")
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": "只回复两个字：正常"}],
        "max_tokens": 16,
        "temperature": 0,
        "stream": False,
    }
    started = time.time()
    response = _post(_endpoint(cfg["base_url"]), payload, api_key, min(30, int(cfg["timeout"])))
    choices = response.get("choices") or []
    content = ""
    if choices:
        content = (choices[0].get("message") or {}).get("content") or ""
    return {
        "model": cfg["model"],
        "upstream_model": response.get("model") or cfg["model"],
        "latency_ms": int((time.time() - started) * 1000),
        "reply": content.strip()[:100],
    }
