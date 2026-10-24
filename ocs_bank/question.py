# -*- coding: utf-8 -*-
"""题目解析、归一化与答案格式转换。

OCS 的答案匹配规则（4.x 源码）：
- 单选题：优先「答案文本 ≈ 选项文本」（归一化精确匹配 / 相似度 > 0.6），
  兜底「纯字母 A」；
- 多选题：答案按 # 等分隔符拆分后逐项匹配选项文本，兜底纯字母（如 ABD）；
- 判断题：答案必须命中「正确/错误」类关键词，没有字母兜底；
- 填空题：按 # 拆分，答案个数需与空格数一致。

因此本服务统一输出「选项文本」（多选用 # 连接），判断题输出「正确/错误」，
对选项顺序变化、选项打乱都更稳。
"""
from __future__ import annotations

import difflib
import hashlib
import html
import re
import unicodedata
from typing import Any, Iterable

TRUE_WORDS = ["正确", "对", "是", "√", "true", "t", "yes", "对的", "正确的", "1"]
FALSE_WORDS = ["错误", "错", "否", "×", "x", "false", "f", "no", "不对", "不正确", "不是", "0"]
JUDGE_WORDS = set(TRUE_WORDS + FALSE_WORDS)

TYPE_ALIASES = {
    "single": "single",
    "单选题": "single",
    "单选": "single",
    "multiple": "multiple",
    "多选题": "multiple",
    "多选": "multiple",
    "judgement": "judgement",
    "judgment": "judgement",
    "判断题": "judgement",
    "判断": "judgement",
    "completion": "completion",
    "填空题": "completion",
    "填空": "completion",
}

TYPE_LABELS = {
    "single": "单选",
    "multiple": "多选",
    "judgement": "判断",
    "completion": "填空",
}

_OPTION_LABEL_RE = re.compile(
    r"^\s*(?:[（(]\s*)?([A-Za-z]|[0-9]{1,2}|[①②③④⑤⑥⑦⑧⑨⑩])\s*(?:[)）])?\s*[.、．:：)）]?\s*(.+)$"
)
_TYPE_TAG_RE = re.compile(
    r"[【\[（(]\s*(?:单选题?|多选题?|不定项选择题?|判断题?|填空题?|简答题?|论述题?|single|multiple|judgement|completion)\s*[】\]）)]",
    re.IGNORECASE,
)
_LEADING_NUM_RE = re.compile(r"^\s*(?:\d{1,3}|[一二三四五六七八九十]{1,3})\s*[.、．:：]\s*")
_WS_RE = re.compile(r"[ \t\u3000]+")
_BLANK_RE = re.compile(r"\n{3,}")
_SAFE_RE = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9]")


# --------------------------------------------------------------------------
# 基础清洗
# --------------------------------------------------------------------------
def strip_html(text: str) -> str:
    if not text:
        return ""
    text = str(text)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WS_RE.sub(" ", text)
    text = _BLANK_RE.sub("\n\n", text)
    return text.strip()


def clean_display(text: str, limit: int = 2000) -> str:
    text = strip_html(text)
    return text[:limit]


def normalize_question(text: str) -> str:
    """用于缓存 Key 的归一化：去题型标签、题号、空白和标点。"""
    text = strip_html(text)
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _TYPE_TAG_RE.sub("", text)
    text = _LEADING_NUM_RE.sub("", text, count=1)
    text = text.lower()
    text = _SAFE_RE.sub("", text)
    return text


def make_key(question: str) -> str:
    normalized = normalize_question(question)
    if not normalized:
        normalized = strip_html(question).strip().lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def normalize_type(raw: str | None) -> str:
    if not raw:
        return ""
    key = str(raw).strip().lower()
    return TYPE_ALIASES.get(key, TYPE_ALIASES.get(str(raw).strip(), ""))


def type_label(qtype: str) -> str:
    return TYPE_LABELS.get(qtype, qtype or "未知")


# --------------------------------------------------------------------------
# 选项解析
# --------------------------------------------------------------------------
def parse_options(raw: Any) -> list[dict[str, str]]:
    """把 OCS 传来的选项字符串（"A. xxx\\nB. yyy"）解析成结构化列表。"""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        lines = [str(item) for item in raw]
    else:
        text = str(raw).replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")

    options: list[dict[str, str]] = []
    for line in lines:
        line = _WS_RE.sub(" ", strip_html(line)).strip()
        if not line:
            continue
        position = len(options)
        match = _OPTION_LABEL_RE.match(line)
        label = ""
        content = line
        if match:
            candidate = match.group(1)
            rest = (match.group(2) or "").strip()
            # 仅当标签确实对应当前序号时才采用，避免把 "3.14 是…" 误判成选项 3
            if rest and _label_matches(candidate, position):
                label = candidate
                content = rest
        if not label:
            label = chr(ord("A") + position) if position < 26 else str(position + 1)
        options.append({"label": label.upper(), "text": content})
    return options


def _label_matches(candidate: str, index: int) -> bool:
    candidate = candidate.strip()
    if candidate.isalpha() and len(candidate) == 1:
        return candidate.upper() == chr(ord("A") + index)
    if candidate in "①②③④⑤⑥⑦⑧⑨⑩":
        return "①②③④⑤⑥⑦⑧⑨⑩".index(candidate) == index
    if candidate.isdigit():
        return int(candidate) == index + 1
    return False


def options_to_text(options: Iterable[dict[str, str]]) -> str:
    return "\n".join(f"{opt['label']}. {opt['text']}" for opt in options)


def looks_like_judgement(options: list[dict[str, str]]) -> bool:
    if len(options) != 2:
        return False
    texts = [opt["text"] for opt in options]
    return any(_judge_of(text) for text in texts) and len({_judge_of(t) for t in texts}) == 2


def _judge_of(text: str) -> str:
    value = _strip_option_label(text).strip().lower()
    value = _SAFE_RE.sub("", value)
    if value in {w.lower() for w in TRUE_WORDS}:
        return "正确"
    if value in {w.lower() for w in FALSE_WORDS}:
        return "错误"
    return ""


def _strip_option_label(text: str) -> str:
    text = _WS_RE.sub(" ", str(text)).strip()
    match = re.match(r"^\s*(?:[（(])?([A-Za-z]|[0-9]{1,2})\s*(?:[)）])?\s*[.、．:：]\s*(.+)$", text)
    return (match.group(2) if match else text).strip()


# --------------------------------------------------------------------------
# 答案转换
# --------------------------------------------------------------------------
def normalize_answer(
    raw_answer: Any,
    qtype: str,
    options: list[dict[str, str]],
    confidence: float | None = None,
) -> tuple[str, float | None]:
    """把模型返回的答案转成 OCS 最容易匹配的格式。

    返回 (answer, confidence)。answer 为空表示无法给出可用答案。
    """
    qtype = normalize_type(qtype)
    tokens = _tokenize(raw_answer, allow_letter_split=bool(options) and qtype in ("", "single", "multiple"))
    if not tokens:
        return "", confidence

    # 判断题：统一输出「正确 / 错误」
    if qtype == "judgement" or (not qtype and looks_like_judgement(options)):
        result = _judge_answer(tokens, options)
        if result:
            return result, confidence
        if looks_like_judgement(options):
            return "", confidence * 0.5 if confidence else None

    # 填空题 / 无选项：按 # 连接
    if qtype == "completion" or not options:
        values = [_clean_token(t) for t in tokens]
        values = [v for v in values if v]
        if not values:
            return "", confidence
        return "#".join(values[:12]), confidence

    # 选择题
    letters: list[str] = []
    for token in tokens:
        letter = _pick_letter(token, options)
        if letter:
            letters.append(letter)
    letters = sorted(set(letters), key=lambda x: ord(x))

    if letters:
        if qtype == "multiple":
            texts = [_option_text_by_letter(letter, options) for letter in letters]
            texts = [t for t in texts if t]
            if texts:
                return "#".join(texts), confidence
        else:
            text = _option_text_by_letter(letters[0], options)
            if text:
                return text, confidence
            # 多选题被误判为单选时，返回全部字母对应文本
            if len(letters) > 1:
                return letters[0], confidence

    # 模型直接给了选项文本
    texts = [_match_option_text(token, options) for token in tokens]
    texts = [t for t in texts if t]
    if texts:
        unique: list[str] = []
        for text in texts:
            if text not in unique:
                unique.append(text)
        return "#".join(unique), confidence

    # 模型给的字母全都落不到选项上（比如 4 个选项却回答 E）：宁可拒答，也不返回错答案
    if options and all(re.fullmatch(r"[A-Za-z]{1,2}", _clean_token(t) or "") for t in tokens):
        return "", confidence

    # 实在匹配不上：原文返回（OCS 会做相似度兜底）
    raw = "#".join(_clean_token(t) for t in tokens if _clean_token(t))
    return raw[:500], confidence


def _tokenize(raw_answer: Any, allow_letter_split: bool = True) -> list[str]:
    if raw_answer is None:
        return []
    if isinstance(raw_answer, (list, tuple)):
        items = [str(x) for x in raw_answer]
    elif isinstance(raw_answer, str):
        text = raw_answer.strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                import json

                parsed = json.loads(text)
                if isinstance(parsed, list):
                    items = [str(x) for x in parsed]
                else:
                    items = [text]
            except ValueError:
                items = [text]
        else:
            items = re.split(r"[#;；\n|]+", text)
    else:
        items = [str(raw_answer)]

    tokens: list[str] = []
    for item in items:
        item = _clean_token(item)
        if not item:
            continue
        # "ABD" / "A、B" 这类合并字母答案拆开（仅选择题）
        compact = re.sub(r"[\s,，、.。;；#|]+", "", item).upper()
        if allow_letter_split and re.fullmatch(r"[A-Z]{2,8}", compact) and len(set(compact)) == len(compact):
            if all(ord(ch) - 65 < 26 for ch in compact):
                tokens.extend(compact)
                continue
        tokens.append(item)
    return tokens


def _clean_token(token: str) -> str:
    token = strip_html(str(token))
    token = re.sub(r"^(?:答案|正确答案|选项)\s*[:：]?\s*", "", token)
    return token.strip().strip("。；;，,")


def _pick_letter(token: str, options: list[dict[str, str]]) -> str:
    token = _clean_token(token)
    if not token:
        return ""
    letters = {opt["label"]: opt for opt in options}
    compact = token.upper().strip(" .。、:：()（）[]【】")
    if re.fullmatch(r"[A-Z]", compact) and compact in letters:
        return compact
    if re.fullmatch(r"[A-Z]", compact):
        index = ord(compact) - 65
        if 0 <= index < len(options):
            return options[index]["label"]

    text = _strip_option_label(token)
    matched = _match_option_text(text, options, threshold=0.72)
    if matched:
        for opt in options:
            if opt["text"] == matched:
                return opt["label"]
    return ""


def _option_text_by_letter(letter: str, options: list[dict[str, str]]) -> str:
    for opt in options:
        if opt["label"] == letter:
            return opt["text"]
    index = ord(letter) - 65
    if 0 <= index < len(options):
        return options[index]["text"]
    return ""


def _match_option_text(token: str, options: list[dict[str, str]], threshold: float = 0.8) -> str:
    target = _SAFE_RE.sub("", _strip_option_label(token).lower())
    if not target:
        return ""
    best_text = ""
    best_ratio = 0.0
    for opt in options:
        candidate = _SAFE_RE.sub("", opt["text"].lower())
        if not candidate:
            continue
        if target == candidate:
            return opt["text"]
        if len(target) >= 2 and (target in candidate or candidate in target):
            ratio = min(len(target), len(candidate)) / max(len(target), len(candidate))
            if ratio >= 0.5 and ratio > best_ratio:
                best_ratio, best_text = ratio, opt["text"]
            continue
        ratio = difflib.SequenceMatcher(None, target, candidate).ratio()
        if ratio > best_ratio:
            best_ratio, best_text = ratio, opt["text"]
    if best_ratio >= threshold:
        return best_text
    return ""


def _judge_answer(tokens: list[str], options: list[dict[str, str]]) -> str:
    for token in tokens:
        text = _strip_option_label(token)
        if text.upper() in {opt["label"] for opt in options}:
            opt = next(o for o in options if o["label"] == text.upper())
            verdict = _judge_of(opt["text"])
            if verdict:
                return verdict
            continue
        verdict = _judge_of(text)
        if verdict:
            return verdict
        lowered = _SAFE_RE.sub("", text.lower())
        for word in TRUE_WORDS:
            if lowered == _SAFE_RE.sub("", word.lower()):
                return "正确"
        for word in FALSE_WORDS:
            if lowered == _SAFE_RE.sub("", word.lower()):
                return "错误"
    return ""


def answer_is_compatible(answer: str, qtype: str, options: list[dict[str, str]]) -> bool:
    """缓存答案是否仍能匹配当前选项（选项被打乱 / 换题时重新问 AI）。"""
    if not answer or not options:
        return True
    qtype = normalize_type(qtype)
    if qtype in ("judgement", "completion") or looks_like_judgement(options):
        return True

    # 纯字母答案（A / AB / A#B / A,B），只要字母都能对上选项就认为兼容
    labels = {opt["label"].upper() for opt in options}
    compact = re.sub(r"[^A-Za-z]", "", answer).upper()
    if compact and len(set(compact)) == len(compact) and all(ch in labels for ch in compact):
        return True

    fragments = [f for f in re.split(r"[#;；\n|]+", answer) if f.strip()]
    if not fragments:
        return False
    for fragment in fragments:
        text = _SAFE_RE.sub("", _strip_option_label(fragment).lower())
        if len(text) == 1 and text.upper() in {opt["label"].lower() for opt in options}:
            continue
        if not text:
            return False
        hit = False
        for opt in options:
            candidate = _SAFE_RE.sub("", opt["text"].lower())
            if not candidate:
                continue
            if text == candidate or (len(text) >= 2 and (text in candidate or candidate in text)):
                hit = True
                break
            if difflib.SequenceMatcher(None, text, candidate).ratio() >= 0.75:
                hit = True
                break
        if not hit:
            return False
    return True
