# -*- coding: utf-8 -*-
"""配置读写。

优先级：环境变量 > data/config.json > 默认值。
API Key 只在本地保存，接口返回时永远打码。
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("OCS_DATA_DIR") or (ROOT / "data"))
CONFIG_PATH = DATA_DIR / "config.json"
DB_PATH = DATA_DIR / "bank.db"
WEB_DIR = ROOT / "web"

DEFAULTS: dict[str, Any] = {
    # DeepSeek（也兼容任何 OpenAI 格式的接口）
    "api_key": "",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "temperature": 0.2,
    "max_tokens": 800,
    "timeout": 60,
    # 题库行为
    "ai_enabled": True,
    "cache_enabled": True,
    "fuzzy_match": False,
    "min_confidence": 0.3,
    # 言溪题库（本地未收录时优先查询）
    "yanxi_enabled": False,
    "yanxi_token": "",
    "yanxi_url": "https://tk.enncy.cn/query",
    "yanxi_timeout": 15,
    # 服务
    "port": 8787,
    "host": "127.0.0.1",
}

_INT_RANGES = {
    "max_tokens": (128, 8000),
    "timeout": (5, 300),
    "yanxi_timeout": (3, 120),
    "port": (1024, 65535),
}
_FLOAT_RANGES = {
    "temperature": (0.0, 2.0),
    "min_confidence": (0.0, 1.0),
}

_lock = threading.Lock()
_cache: dict[str, Any] | None = None


def _coerce(key: str, value: Any) -> Any:
    if key in _INT_RANGES:
        lo, hi = _INT_RANGES[key]
        try:
            return max(lo, min(hi, int(value)))
        except (TypeError, ValueError):
            return DEFAULTS[key]
    if key in _FLOAT_RANGES:
        lo, hi = _FLOAT_RANGES[key]
        try:
            return round(max(lo, min(hi, float(value))), 2)
        except (TypeError, ValueError):
            return DEFAULTS[key]
    if isinstance(DEFAULTS.get(key), bool):
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on", "是", "开")
        return bool(value)
    return value


def _read_file() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, ValueError):
        return {}


def load_config(refresh: bool = False) -> dict[str, Any]:
    """返回完整配置（含真实 Key，仅供内部使用）。"""
    global _cache
    with _lock:
        if _cache is not None and not refresh:
            return dict(_cache)
        cfg = dict(DEFAULTS)
        for key, value in _read_file().items():
            if key in DEFAULTS:
                cfg[key] = _coerce(key, value)
        # 环境变量优先
        if os.environ.get("DEEPSEEK_API_KEY"):
            cfg["api_key"] = os.environ["DEEPSEEK_API_KEY"].strip()
            cfg["api_key_source"] = "env"
        if os.environ.get("DEEPSEEK_BASE_URL"):
            cfg["base_url"] = os.environ["DEEPSEEK_BASE_URL"].strip()
        if os.environ.get("DEEPSEEK_MODEL"):
            cfg["model"] = os.environ["DEEPSEEK_MODEL"].strip()
        if os.environ.get("PORT"):
            try:
                cfg["port"] = _coerce("port", os.environ["PORT"])
            except ValueError:
                pass
        _cache = cfg
        return dict(cfg)


def save_config(patch: dict[str, Any]) -> dict[str, Any]:
    """合并保存配置（只接受已知字段）。"""
    global _cache
    with _lock:
        current = _read_file()
        for key, value in patch.items():
            if key not in DEFAULTS:
                continue
            if key == "api_key" and isinstance(value, str):
                value = value.strip()
            current[key] = _coerce(key, value)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _cache = None
    return load_config(refresh=True)


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 10:
        return key[:2] + "*" * max(1, len(key) - 2)
    return f"{key[:5]}{'*' * 8}{key[-4:]}"


def public_config() -> dict[str, Any]:
    """给前端用的配置（Key 打码）。"""
    cfg = load_config()
    key = cfg.get("api_key", "")
    return {
        "api_key_set": bool(key),
        "api_key_masked": mask_key(key),
        "api_key_source": cfg.get("api_key_source", "file" if key else ""),
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
        "timeout": cfg["timeout"],
        "ai_enabled": cfg["ai_enabled"],
        "cache_enabled": cfg["cache_enabled"],
        "fuzzy_match": cfg["fuzzy_match"],
        "min_confidence": cfg["min_confidence"],
        "yanxi_enabled": cfg["yanxi_enabled"],
        "yanxi_url": cfg["yanxi_url"],
        "yanxi_timeout": cfg["yanxi_timeout"],
        "yanxi_token_set": bool((cfg.get("yanxi_token") or "").strip()),
        "yanxi_token_masked": mask_key((cfg.get("yanxi_token") or "").strip()),
        "port": cfg["port"],
    }
