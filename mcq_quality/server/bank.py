"""
bank.py — SQLite storage for the MCQ question bank.

Used by the MCP server's bank_* tools. The bank persists across conversations
and across AI clients: that's what makes the server paradigm fit here, where
a skill alone could not.

Schema:
- items: current state of each item (one row per item)
- item_versions: snapshot of every change (audit trail)

Default DB location: ~/.mcq-quality/bank.db
Override with MCQ_BANK_DB_PATH environment variable.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def get_db_path() -> Path:
    """Resolve the database path, creating parent dir if needed."""
    custom = os.environ.get("MCQ_BANK_DB_PATH")
    if custom:
        path = Path(custom).expanduser()
    else:
        path = Path.home() / ".mcq-quality" / "bank.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stem TEXT NOT NULL,
    options_json TEXT NOT NULL,
    correct_index INTEGER NOT NULL,
    learning_objective TEXT,
    blooms_level TEXT,
    category TEXT,
    tags_json TEXT,
    rationales_json TEXT,
    learner_feedback_json TEXT,
    misconception_tags_json TEXT,
    quality_status TEXT,
    audit_results_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    deleted INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS item_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    changed_by TEXT,
    change_note TEXT,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(quality_status);
CREATE INDEX IF NOT EXISTS idx_items_blooms ON items(blooms_level);
CREATE INDEX IF NOT EXISTS idx_items_deleted ON items(deleted);
CREATE INDEX IF NOT EXISTS idx_versions_item ON item_versions(item_id);
"""


def get_conn(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open a connection with row factory and FK enforcement."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize schema. Idempotent."""
    conn = get_conn(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a row to a dict, decoding JSON columns."""
    d = dict(row)
    for json_col in (
        "options_json", "tags_json", "rationales_json",
        "learner_feedback_json", "misconception_tags_json", "audit_results_json"
    ):
        if json_col in d and d[json_col] is not None:
            try:
                d[json_col.removesuffix("_json")] = json.loads(d[json_col])
            except (json.JSONDecodeError, TypeError):
                d[json_col.removesuffix("_json")] = None
            del d[json_col]
        elif json_col in d:
            d[json_col.removesuffix("_json")] = None
            del d[json_col]
    return d


def add_item(
    stem: str,
    options: list[str],
    correct_index: int,
    learning_objective: Optional[str] = None,
    blooms_level: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    rationales: Optional[dict] = None,
    learner_feedback: Optional[dict] = None,
    misconception_tags: Optional[list[str]] = None,
    quality_status: Optional[str] = None,
    audit_results: Optional[dict] = None,
    created_by: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Insert a new item. Returns the inserted row as a dict."""
    conn = get_conn(db_path)
    try:
        ts = now_iso()
        cursor = conn.execute(
            """
            INSERT INTO items (
                stem, options_json, correct_index, learning_objective, blooms_level,
                category, tags_json, rationales_json, learner_feedback_json,
                misconception_tags_json, quality_status, audit_results_json,
                created_at, updated_at, created_by, version, deleted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
            """,
            (
                stem,
                json.dumps(options),
                correct_index,
                learning_objective,
                blooms_level,
                category,
                json.dumps(tags) if tags is not None else None,
                json.dumps(rationales) if rationales is not None else None,
                json.dumps(learner_feedback) if learner_feedback is not None else None,
                json.dumps(misconception_tags) if misconception_tags is not None else None,
                quality_status,
                json.dumps(audit_results) if audit_results is not None else None,
                ts, ts, created_by,
            ),
        )
        item_id = cursor.lastrowid
        # Snapshot version 1
        snapshot = _build_snapshot(
            item_id, stem, options, correct_index, learning_objective, blooms_level,
            category, tags, rationales, learner_feedback, misconception_tags,
            quality_status, audit_results, ts, ts, created_by, 1
        )
        conn.execute(
            """
            INSERT INTO item_versions (item_id, version, snapshot_json, changed_at, changed_by, change_note)
            VALUES (?, 1, ?, ?, ?, ?)
            """,
            (item_id, json.dumps(snapshot), ts, created_by, "Initial version"),
        )
        conn.commit()
        return get_item(item_id, db_path=db_path)
    finally:
        conn.close()


def _build_snapshot(item_id, stem, options, correct_index, lo, blooms, category, tags,
                    rationales, feedback, misc_tags, status, audit, created, updated,
                    by, version) -> dict:
    return {
        "id": item_id, "stem": stem, "options": options, "correct_index": correct_index,
        "learning_objective": lo, "blooms_level": blooms, "category": category,
        "tags": tags, "rationales": rationales, "learner_feedback": feedback,
        "misconception_tags": misc_tags, "quality_status": status,
        "audit_results": audit, "created_at": created, "updated_at": updated,
        "created_by": by, "version": version,
    }


def get_item(item_id: int, *, include_deleted: bool = False, db_path: Optional[Path] = None) -> Optional[dict[str, Any]]:
    """Retrieve a single item by ID."""
    conn = get_conn(db_path)
    try:
        if include_deleted:
            row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM items WHERE id = ? AND deleted = 0", (item_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def list_items(
    *,
    category: Optional[str] = None,
    blooms_level: Optional[str] = None,
    quality_status: Optional[str] = None,
    tag: Optional[str] = None,
    include_deleted: bool = False,
    limit: int = 100,
    offset: int = 0,
    db_path: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """List items with optional filters."""
    conn = get_conn(db_path)
    try:
        clauses = []
        params: list[Any] = []
        if not include_deleted:
            clauses.append("deleted = 0")
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if blooms_level is not None:
            clauses.append("blooms_level = ?")
            params.append(blooms_level)
        if quality_status is not None:
            clauses.append("quality_status = ?")
            params.append(quality_status)
        if tag is not None:
            clauses.append("tags_json LIKE ?")
            params.append(f'%"{tag}"%')
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        params.extend([limit, offset])
        rows = conn.execute(
            f"SELECT * FROM items {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def search_items(query: str, *, limit: int = 20, db_path: Optional[Path] = None) -> list[dict[str, Any]]:
    """Text search across stem and options. Case-insensitive substring match."""
    conn = get_conn(db_path)
    try:
        like = f"%{query}%"
        rows = conn.execute(
            """
            SELECT * FROM items
            WHERE deleted = 0 AND (stem LIKE ? OR options_json LIKE ?)
            ORDER BY updated_at DESC LIMIT ?
            """,
            (like, like, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def update_item(
    item_id: int,
    *,
    changed_by: Optional[str] = None,
    change_note: Optional[str] = None,
    db_path: Optional[Path] = None,
    **fields,
) -> Optional[dict[str, Any]]:
    """
    Update fields on an item. Bumps version, snapshots prior state.
    Allowed fields: stem, options, correct_index, learning_objective, blooms_level,
    category, tags, rationales, learner_feedback, misconception_tags,
    quality_status, audit_results.
    """
    allowed = {
        "stem", "options", "correct_index", "learning_objective", "blooms_level",
        "category", "tags", "rationales", "learner_feedback", "misconception_tags",
        "quality_status", "audit_results",
    }
    bad = set(fields) - allowed
    if bad:
        raise ValueError(f"Unknown fields: {bad}")

    current = get_item(item_id, db_path=db_path)
    if current is None:
        return None

    # JSON-encode mutable fields
    json_fields = {"options", "tags", "rationales", "learner_feedback", "misconception_tags", "audit_results"}
    set_clauses = []
    params: list[Any] = []
    for k, v in fields.items():
        col = f"{k}_json" if k in json_fields else k
        set_clauses.append(f"{col} = ?")
        params.append(json.dumps(v) if k in json_fields else v)

    new_version = current["version"] + 1
    ts = now_iso()
    set_clauses.append("updated_at = ?")
    params.append(ts)
    set_clauses.append("version = ?")
    params.append(new_version)
    params.append(item_id)

    conn = get_conn(db_path)
    try:
        conn.execute(
            f"UPDATE items SET {', '.join(set_clauses)} WHERE id = ?",
            params,
        )
        conn.commit()  # commit so get_item sees the update
        # Snapshot the new state
        updated = get_item(item_id, db_path=db_path)
        conn.execute(
            """
            INSERT INTO item_versions (item_id, version, snapshot_json, changed_at, changed_by, change_note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (item_id, new_version, json.dumps(updated), ts, changed_by, change_note),
        )
        conn.commit()
        return updated
    finally:
        conn.close()


def delete_item(item_id: int, *, hard: bool = False, db_path: Optional[Path] = None) -> bool:
    """Delete an item. Soft delete by default; hard delete removes the row entirely."""
    conn = get_conn(db_path)
    try:
        if hard:
            cursor = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        else:
            cursor = conn.execute(
                "UPDATE items SET deleted = 1, updated_at = ? WHERE id = ? AND deleted = 0",
                (now_iso(), item_id),
            )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_history(item_id: int, db_path: Optional[Path] = None) -> list[dict[str, Any]]:
    """Return all version snapshots for an item, oldest first."""
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            """
            SELECT version, snapshot_json, changed_at, changed_by, change_note
            FROM item_versions WHERE item_id = ? ORDER BY version ASC
            """,
            (item_id,),
        ).fetchall()
        return [
            {
                "version": r["version"],
                "snapshot": json.loads(r["snapshot_json"]),
                "changed_at": r["changed_at"],
                "changed_by": r["changed_by"],
                "change_note": r["change_note"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_stats(db_path: Optional[Path] = None) -> dict[str, Any]:
    """Aggregate stats across the bank."""
    conn = get_conn(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) as n FROM items WHERE deleted = 0").fetchone()["n"]

        by_category = {
            r["category"] or "(uncategorized)": r["n"]
            for r in conn.execute(
                "SELECT category, COUNT(*) as n FROM items WHERE deleted = 0 GROUP BY category"
            ).fetchall()
        }
        by_status = {
            r["quality_status"] or "(none)": r["n"]
            for r in conn.execute(
                "SELECT quality_status, COUNT(*) as n FROM items WHERE deleted = 0 GROUP BY quality_status"
            ).fetchall()
        }
        by_blooms = {
            r["blooms_level"] or "(none)": r["n"]
            for r in conn.execute(
                "SELECT blooms_level, COUNT(*) as n FROM items WHERE deleted = 0 GROUP BY blooms_level"
            ).fetchall()
        }
        return {
            "total_items": total,
            "by_category": by_category,
            "by_quality_status": by_status,
            "by_blooms_level": by_blooms,
        }
    finally:
        conn.close()
