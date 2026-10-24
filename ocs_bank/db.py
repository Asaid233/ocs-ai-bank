# -*- coding: utf-8 -*-
"""SQLite 题库存储。"""
from __future__ import annotations

import csv
import io
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterable, Iterator

from .config import DB_PATH, DATA_DIR

_init_lock = threading.Lock()
_initialized = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    qkey        TEXT NOT NULL UNIQUE,
    question    TEXT NOT NULL,
    options     TEXT NOT NULL DEFAULT '',
    qtype       TEXT NOT NULL DEFAULT '',
    answer      TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'ai',
    confidence  REAL,
    hits        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_questions_updated ON questions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_questions_type ON questions(qtype);

CREATE TABLE IF NOT EXISTS logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    question    TEXT NOT NULL,
    qtype       TEXT NOT NULL DEFAULT '',
    answer      TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT '',
    confidence  REAL,
    elapsed_ms  INTEGER NOT NULL DEFAULT 0,
    tokens      INTEGER NOT NULL DEFAULT 0,
    success     INTEGER NOT NULL DEFAULT 1,
    message     TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_logs_ts ON logs(ts DESC);
"""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    global _initialized
    with _init_lock:
        if _initialized:
            return
        with connect() as conn:
            conn.executescript(SCHEMA)
        _initialized = True


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


# --------------------------------------------------------------------------
# 查询
# --------------------------------------------------------------------------
def get_by_key(qkey: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM questions WHERE qkey = ?", (qkey,)).fetchone()
        return _row_to_dict(row) if row else None


def get_by_id(item_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (item_id,)).fetchone()
        return _row_to_dict(row) if row else None


def list_questions(
    keyword: str = "",
    qtype: str = "",
    source: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    where: list[str] = []
    params: list[Any] = []
    if keyword:
        where.append("(question LIKE ? OR answer LIKE ?)")
        like = f"%{keyword}%"
        params.extend([like, like])
    if qtype:
        where.append("qtype = ?")
        params.append(qtype)
    if source:
        where.append("source = ?")
        params.append(source)
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    page = max(1, int(page))
    page_size = max(1, min(200, int(page_size)))
    offset = (page - 1) * page_size

    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM questions {clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM questions {clause} ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
            [*params, page_size, offset],
        ).fetchall()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
        "items": [_row_to_dict(r) for r in rows],
    }


def fuzzy_candidates(limit: int = 4000) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM questions ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def all_questions() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM questions ORDER BY id").fetchall()
    return [_row_to_dict(r) for r in rows]


# --------------------------------------------------------------------------
# 写入
# --------------------------------------------------------------------------
def upsert_question(
    qkey: str,
    question: str,
    answer: str,
    options: str = "",
    qtype: str = "",
    source: str = "ai",
    confidence: float | None = None,
) -> int:
    ts = now_iso()
    with connect() as conn:
        row = conn.execute("SELECT id FROM questions WHERE qkey = ?", (qkey,)).fetchone()
        if row:
            conn.execute(
                """UPDATE questions
                   SET question = ?, options = ?, qtype = ?, answer = ?, confidence = ?,
                       source = ?, updated_at = ?
                   WHERE id = ?""",
                (question, options, qtype, answer, confidence, source, ts, row["id"]),
            )
            return int(row["id"])
        cur = conn.execute(
            """INSERT INTO questions (qkey, question, options, qtype, answer, source, confidence, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (qkey, question, options, qtype, answer, source, confidence, ts, ts),
        )
        return int(cur.lastrowid)


def update_question(item_id: int, patch: dict[str, Any]) -> bool:
    allowed = ["question", "qkey", "options", "qtype", "answer", "source", "confidence"]
    sets: list[str] = []
    params: list[Any] = []
    for key in allowed:
        if key in patch and patch[key] is not None:
            sets.append(f"{key} = ?")
            params.append(patch[key])
    if not sets:
        return False
    sets.append("updated_at = ?")
    params.append(now_iso())
    params.append(item_id)
    with connect() as conn:
        cur = conn.execute(f"UPDATE questions SET {', '.join(sets)} WHERE id = ?", params)
        return cur.rowcount > 0


def delete_question(item_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM questions WHERE id = ?", (item_id,))
        return cur.rowcount > 0


def touch_hit(item_id: int) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE questions SET hits = hits + 1, updated_at = updated_at WHERE id = ?",
            (item_id,),
        )


def import_items(items: Iterable[dict[str, Any]], source: str = "import") -> dict[str, int]:
    inserted = updated = skipped = 0
    ts = now_iso()
    with connect() as conn:
        for item in items:
            question = str(item.get("question") or item.get("title") or "").strip()
            answer = str(item.get("answer") or "").strip()
            if not question or not answer:
                skipped += 1
                continue
            qkey = str(item.get("qkey") or "").strip() or _fallback_key(question)
            options = str(item.get("options") or "")
            qtype = str(item.get("qtype") or item.get("type") or "")[:20]
            confidence = item.get("confidence")
            try:
                confidence = float(confidence) if confidence is not None else None
            except (TypeError, ValueError):
                confidence = None

            row = conn.execute("SELECT id FROM questions WHERE qkey = ?", (qkey,)).fetchone()
            if row:
                conn.execute(
                    """UPDATE questions SET question = ?, options = ?, qtype = ?, answer = ?,
                           source = ?, confidence = ?, updated_at = ? WHERE id = ?""",
                    (question, options, qtype, answer, source, confidence, ts, row["id"]),
                )
                updated += 1
            else:
                conn.execute(
                    """INSERT INTO questions (qkey, question, options, qtype, answer, source, confidence, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (qkey, question, options, qtype, answer, source, confidence, ts, ts),
                )
                inserted += 1
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


def _fallback_key(question: str) -> str:
    # import 时未提供 qkey 的兜底（正常路径由 question.make_key 生成）
    import hashlib

    return hashlib.sha1(question.strip().encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# 日志 / 统计
# --------------------------------------------------------------------------
def log_request(
    question: str,
    qtype: str,
    answer: str,
    source: str,
    confidence: float | None,
    elapsed_ms: int,
    tokens: int,
    success: bool,
    message: str = "",
) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO logs (ts, question, qtype, answer, source, confidence, elapsed_ms, tokens, success, message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                now_iso(),
                question[:500],
                qtype,
                answer[:500],
                source,
                confidence,
                int(elapsed_ms),
                int(tokens),
                1 if success else 0,
                message[:300],
            ),
        )
        # 只保留最近 5000 条日志
        conn.execute(
            "DELETE FROM logs WHERE id NOT IN (SELECT id FROM logs ORDER BY id DESC LIMIT 5000)"
        )


def stats() -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        new_today = conn.execute(
            "SELECT COUNT(*) FROM questions WHERE created_at LIKE ?", (f"{today}%",)
        ).fetchone()[0]
        agg = conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN source = 'bank' THEN 1 ELSE 0 END) AS bank_hits,
                      SUM(CASE WHEN source = 'ai' THEN 1 ELSE 0 END) AS ai_calls,
                      SUM(CASE WHEN source = 'yanxi' THEN 1 ELSE 0 END) AS yanxi_hits,
                      SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failures,
                      COALESCE(SUM(tokens), 0) AS tokens,
                      COALESCE(AVG(elapsed_ms), 0) AS avg_ms
               FROM logs WHERE ts LIKE ?""",
            (f"{today}%",),
        ).fetchone()
        type_rows = conn.execute(
            "SELECT qtype, COUNT(*) AS n FROM questions GROUP BY qtype ORDER BY n DESC"
        ).fetchall()
        top_rows = conn.execute(
            "SELECT id, question, hits FROM questions WHERE hits > 0 ORDER BY hits DESC LIMIT 5"
        ).fetchall()

    today_total = int(agg["total"] or 0)
    bank_hits = int(agg["bank_hits"] or 0)
    ai_calls = int(agg["ai_calls"] or 0)
    return {
        "total_questions": int(total),
        "new_today": int(new_today),
        "today_total": today_total,
        "today_bank_hits": bank_hits,
        "today_ai_calls": ai_calls,
        "today_yanxi_hits": int(agg["yanxi_hits"] or 0),
        "today_failures": int(agg["failures"] or 0),
        "today_tokens": int(agg["tokens"] or 0),
        "avg_ms": int(agg["avg_ms"] or 0),
        "hit_rate": round((bank_hits + int(agg["yanxi_hits"] or 0)) / today_total, 4) if today_total else 0.0,
        "types": [{"type": r["qtype"] or "unknown", "count": r["n"]} for r in type_rows],
        "top": [_row_to_dict(r) for r in top_rows],
    }


def recent_logs(limit: int = 12) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (max(1, min(100, limit)),)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def export_csv() -> bytes:
    with connect() as conn:
        rows = conn.execute(
            "SELECT question, options, qtype, answer, source, confidence, hits, created_at FROM questions ORDER BY id"
        ).fetchall()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["question", "options", "type", "answer", "source", "confidence", "hits", "created_at"])
    for row in rows:
        writer.writerow([row["question"], row["options"], row["qtype"], row["answer"], row["source"], row["confidence"], row["hits"], row["created_at"]])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")
