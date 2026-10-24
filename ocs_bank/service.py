# -*- coding: utf-8 -*-
"""答题主流程：本地题库命中 -> 相似题 -> DeepSeek 兜底 -> 回写题库。"""
from __future__ import annotations

import difflib
import time
from typing import Any

from . import db
from .config import load_config
from .deepseek import AIError, ask
from .question import (
    answer_is_compatible,
    clean_display,
    make_key,
    normalize_answer,
    normalize_question,
    normalize_type,
    options_to_text,
    parse_options,
)
from .yanxi import YanxiError
from .yanxi import query as yanxi_query

MIN_QUESTION_LEN = 2


def _elapsed(started: float) -> int:
    return int((time.time() - started) * 1000)


def _hit(item: dict[str, Any], started: float, source: str = "bank") -> dict[str, Any]:
    return {
        "code": 1,
        "question": item["question"],
        "answer": item["answer"],
        "source": source,
        "confidence": item.get("confidence"),
        "cached": True,
        "elapsed_ms": _elapsed(started),
        "msg": "本地题库命中",
    }


def _miss(message: str, started: float, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    result = {"code": 0, "msg": message, "elapsed_ms": _elapsed(started)}
    if extra:
        result.update(extra)
    return result


def answer_question(
    title: str,
    options_raw: Any = "",
    qtype: str = "",
    *,
    use_cache: bool | None = None,
    use_ai: bool = True,
) -> dict[str, Any]:
    started = time.time()
    cfg = load_config()
    question = clean_display(title)
    if len(question) < MIN_QUESTION_LEN:
        return _miss("题目内容为空", started)

    qtype = normalize_type(qtype)
    options = parse_options(options_raw)
    options_text = options_to_text(options)
    qkey = make_key(question)
    cache_on = cfg["cache_enabled"] if use_cache is None else use_cache

    # 1) 精确命中本地题库
    if cache_on:
        item = db.get_by_key(qkey)
        if item and answer_is_compatible(item["answer"], item["qtype"] or qtype, options):
            db.touch_hit(int(item["id"]))
            db.log_request(question, qtype or item["qtype"], item["answer"], "bank",
                           item.get("confidence"), _elapsed(started), 0, True, "cache hit")
            return _hit(item, started)

        # 2) 相似题（可选）
        if cfg["fuzzy_match"] and not item:
            similar, ratio = find_similar(question, options, qtype)
            if similar:
                db.touch_hit(int(similar["id"]))
                db.log_request(question, qtype or similar["qtype"], similar["answer"], "bank",
                               similar.get("confidence"), _elapsed(started), 0, True, f"fuzzy {ratio:.2f}")
                result = _hit(similar, started, source="bank")
                result["msg"] = f"命中相似题（{ratio:.0%}）"
                result["similarity"] = round(ratio, 3)
                return result

    # 3) 言溪题库：本地未收录时优先查，命中后直接返回并缓存
    yanxi_note = ""
    if cfg["yanxi_enabled"]:
        if not (cfg.get("yanxi_token") or "").strip():
            yanxi_note = "言溪未配置 Token"
        else:
            try:
                hit = yanxi_query(question, options_text, qtype)
            except YanxiError as exc:
                yanxi_note = f"言溪：{exc}"
            else:
                if hit:
                    answer = hit["answer"]
                    confidence = 0.6 if hit["ai"] else 0.95
                    if cache_on:
                        db.upsert_question(qkey, question, answer, options_text, qtype, "yanxi", confidence)
                    db.log_request(
                        question, qtype, answer, "yanxi", confidence, _elapsed(started), 0, True,
                        f"ai={hit['ai']} times={hit['times']}",
                    )
                    return {
                        "code": 1,
                        "question": question,
                        "answer": answer,
                        "source": "yanxi",
                        "confidence": confidence,
                        "cached": False,
                        "elapsed_ms": _elapsed(started),
                        "msg": "言溪题库命中" + ("（AI 答案）" if hit["ai"] else ""),
                    }
                yanxi_note = "言溪未收录"

    if not use_ai:
        return _miss("本地题库未收录" + (f"；{yanxi_note}" if yanxi_note else "") + "，已跳过 AI", started)

    # 4) AI 兜底
    if not cfg["ai_enabled"]:
        return _miss("本地题库未收录" + (f"；{yanxi_note}" if yanxi_note else "") + "；AI 答题已在设置中关闭", started)
    if not (cfg.get("api_key") or "").strip():
        return _miss(
            "本地题库未收录" + (f"；{yanxi_note}" if yanxi_note else "") + "；尚未配置 DeepSeek API Key",
            started,
        )

    try:
        result = ask(question, options_text, qtype)
    except AIError as exc:
        db.log_request(question, qtype, "", "ai", None, _elapsed(started), 0, False, str(exc))
        return _miss(str(exc), started)
    except Exception as exc:  # noqa: BLE001
        db.log_request(question, qtype, "", "ai", None, _elapsed(started), 0, False, repr(exc))
        return _miss(f"AI 调用异常：{exc}", started)

    answer, confidence = normalize_answer(result.get("answer"), qtype, options, result.get("confidence"))
    if not answer:
        db.log_request(question, qtype, "", "ai", result.get("confidence"), _elapsed(started),
                       result.get("tokens", 0), False, "AI 未给出可用答案")
        return _miss("AI 没有给出可用答案，建议手动作答", started)

    # 4) 低置信度：不写库、不返回，避免污染题库
    if confidence is not None and confidence < cfg["min_confidence"]:
        db.log_request(question, qtype, answer, "ai", confidence, _elapsed(started),
                       result.get("tokens", 0), False, "low confidence")
        return _miss(
            f"AI 置信度过低（{confidence:.2f}），已跳过以免答错",
            started,
            {"low_confidence_answer": answer},
        )

    if cache_on:
        db.upsert_question(qkey, question, answer, options_text, qtype, "ai", confidence)
    log_note = result.get("reason", "")[:120]
    if yanxi_note:
        log_note = f"{log_note} | {yanxi_note}"[:300]
    db.log_request(question, qtype, answer, "ai", confidence, _elapsed(started),
                   result.get("tokens", 0), True, log_note)
    return {
        "code": 1,
        "question": question,
        "answer": answer,
        "source": "ai",
        "confidence": confidence,
        "cached": False,
        "elapsed_ms": _elapsed(started),
        "reason": result.get("reason", ""),
        "msg": "DeepSeek 作答",
    }


def find_similar(
    question: str, options: list[dict[str, str]], qtype: str
) -> tuple[dict[str, Any] | None, float]:
    target = normalize_question(question)
    if not target:
        return None, 0.0
    best: dict[str, Any] | None = None
    best_ratio = 0.0
    for item in db.fuzzy_candidates(4000):
        candidate = normalize_question(item["question"])
        if not candidate:
            continue
        if abs(len(candidate) - len(target)) > max(8, int(len(target) * 0.3)):
            continue
        ratio = difflib.SequenceMatcher(None, target, candidate).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best = item
    if best and best_ratio >= 0.94 and answer_is_compatible(best["answer"], best["qtype"] or qtype, options):
        return best, best_ratio
    return None, 0.0


def test_answer(title: str, options_raw: Any, qtype: str) -> dict[str, Any]:
    """设置页 / 快速测试：强制走 AI，并返回模型原始信息。"""
    started = time.time()
    question = clean_display(title)
    if not question:
        return _miss("请输入题目", started)
    qtype = normalize_type(qtype)
    options = parse_options(options_raw)
    try:
        result = ask(question, options_to_text(options), qtype, force=True)
    except AIError as exc:
        return _miss(str(exc), started)
    answer, confidence = normalize_answer(result.get("answer"), qtype, options, result.get("confidence"))
    return {
        "code": 1 if answer else 0,
        "question": question,
        "answer": answer,
        "raw_answer": result.get("answer"),
        "confidence": confidence,
        "reason": result.get("reason", ""),
        "tokens": result.get("tokens", 0),
        "model": result.get("model", ""),
        "elapsed_ms": _elapsed(started),
        "msg": "" if answer else "模型未给出可用答案",
    }
