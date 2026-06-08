from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from .models import BoundingBox, Detection, SessionInfo


class Storage:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    work_id TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL REFERENCES sessions(id),
                    kind TEXT NOT NULL,
                    path TEXT NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS detections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL REFERENCES sessions(id),
                    image_id INTEGER NOT NULL REFERENCES images(id),
                    label TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    box_json TEXT NOT NULL,
                    polygon_json TEXT,
                    area_pixels REAL,
                    action TEXT NOT NULL,
                    recommendation TEXT NOT NULL,
                    source TEXT NOT NULL,
                    quadrant TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL REFERENCES sessions(id),
                    detection_id INTEGER,
                    action_type TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._ensure_column(conn, "detections", "polygon_json", "TEXT")
            self._ensure_column(conn, "detections", "area_pixels", "REAL")

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def create_session(self, work_id: str, operator: str, notes: str = "") -> SessionInfo:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO sessions (work_id, operator, notes, created_at) VALUES (?, ?, ?, ?)",
                (work_id.strip() or "obra-sin-id", operator.strip() or "operador", notes.strip(), now),
            )
            session_id = int(cur.lastrowid)
        return SessionInfo(
            id=session_id,
            work_id=work_id.strip() or "obra-sin-id",
            operator=operator.strip() or "operador",
            notes=notes.strip(),
            created_at=datetime.fromisoformat(now),
        )

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_session(self, session_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise KeyError(f"Sesion no encontrada: {session_id}")
        return dict(row)

    def complete_session(self, session_id: int) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                "UPDATE sessions SET status = 'complete', completed_at = ? WHERE id = ?",
                (now, session_id),
            )

    def add_image(self, session_id: int, kind: str, path: str | Path, width: int, height: int) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO images (session_id, kind, path, width, height, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, kind, str(path), int(width), int(height), now),
            )
            return int(cur.lastrowid)

    def latest_image(self, session_id: int, kinds: tuple[str, ...] = ("initial", "analysis")) -> dict[str, Any] | None:
        placeholders = ",".join("?" for _ in kinds)
        with self.connect() as conn:
            row = conn.execute(
                f"""
                SELECT * FROM images
                WHERE session_id = ? AND kind IN ({placeholders})
                ORDER BY id DESC LIMIT 1
                """,
                (session_id, *kinds),
            ).fetchone()
        return dict(row) if row else None

    def add_detection(
        self,
        session_id: int,
        image_id: int,
        detection: Detection,
        image_width: int,
        image_height: int,
    ) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        quadrant = detection.quadrant(image_width, image_height)
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO detections (
                    session_id, image_id, label, confidence, box_json, polygon_json,
                    area_pixels, action, recommendation, source, quadrant, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    image_id,
                    detection.label,
                    float(detection.confidence),
                    json.dumps(detection.box.to_dict(), ensure_ascii=False),
                    json.dumps(detection.polygon, ensure_ascii=False) if detection.polygon else None,
                    float(detection.area_pixels) if detection.area_pixels is not None else None,
                    detection.action,
                    detection.recommendation,
                    detection.source,
                    quadrant,
                    now,
                ),
            )
            detection_id = int(cur.lastrowid)
        detection.id = detection_id
        return detection_id

    def list_detections(self, session_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM detections WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["box"] = json.loads(item.pop("box_json"))
            polygon_json = item.pop("polygon_json", None)
            item["polygon"] = json.loads(polygon_json) if polygon_json else None
            result.append(item)
        return result

    def get_detection(self, detection_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM detections WHERE id = ?", (detection_id,)).fetchone()
        if row is None:
            raise KeyError(f"Deteccion no encontrada: {detection_id}")
        item = dict(row)
        item["box"] = json.loads(item.pop("box_json"))
        polygon_json = item.pop("polygon_json", None)
        item["polygon"] = json.loads(polygon_json) if polygon_json else None
        return item

    def log_action(
        self,
        session_id: int,
        action_type: str,
        details: dict[str, Any],
        detection_id: int | None = None,
    ) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO actions (session_id, detection_id, action_type, details_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, detection_id, action_type, json.dumps(details, ensure_ascii=False), now),
            )
            return int(cur.lastrowid)

    def list_actions(self, session_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM actions WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item.pop("details_json"))
            result.append(item)
        return result

    def session_bundle(self, session_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            images = conn.execute("SELECT * FROM images WHERE session_id = ? ORDER BY id ASC", (session_id,)).fetchall()
        if session is None:
            raise KeyError(f"Sesion no encontrada: {session_id}")
        return {
            "session": dict(session),
            "images": [dict(row) for row in images],
            "detections": self.list_detections(session_id),
            "actions": self.list_actions(session_id),
        }


def detection_from_row(row: dict[str, Any]) -> Detection:
    box = row["box"]
    return Detection(
        id=int(row["id"]),
        label=str(row["label"]),
        confidence=float(row["confidence"]),
        box=BoundingBox(int(box["x"]), int(box["y"]), int(box["width"]), int(box["height"])),
        action=str(row["action"]),
        recommendation=str(row["recommendation"]),
        source=str(row.get("source", "storage")),
        polygon=[(int(x), int(y)) for x, y in row["polygon"]] if row.get("polygon") else None,
        area_pixels=float(row["area_pixels"]) if row.get("area_pixels") is not None else None,
    )
