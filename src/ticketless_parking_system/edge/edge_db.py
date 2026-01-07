from __future__ import annotations

import sqlite3
from datetime import datetime


class ParkingDatabase:
    """Tiny wrapper around SQLite for parking sessions."""

    def __init__(self, db_path: str, car_park_id: str):
        self.db_path = db_path
        self.car_park_id = car_park_id
        # check_same_thread=False because we may hit this from different asyncio tasks
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def init_db(self) -> None:
        cur = self.conn.cursor()

        # One row per parking visit
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS parking_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate TEXT NOT NULL,
                car_park_id TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                exit_time TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        # Helpful index for lookups
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_plate_status
            ON parking_sessions (car_park_id, plate, status)
            """
        )

        self.conn.commit()

    @staticmethod
    def _now_iso() -> str:
        # UTC ISO8601 with seconds, plus 'Z' to make it explicit
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"

    def get_active_session(self, plate: str):
        """Return the most recent 'inside' session for this plate in this car park, or None."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM parking_sessions
            WHERE plate = ? AND car_park_id = ? AND status = 'inside'
            ORDER BY entry_time DESC
            LIMIT 1
            """,
            (plate, self.car_park_id),
        )
        return cur.fetchone()  # sqlite3.Row or None

    def has_active_session(self, plate: str) -> bool:
        return self.get_active_session(plate) is not None

    def register_entry(self, plate: str) -> None:
        """Create a new 'inside' session if none exists yet."""
        if self.has_active_session(plate):
            print(f"[DB] Active session already exists for plate={plate}, skipping new entry row.")
            return

        now = self._now_iso()
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO parking_sessions
                (plate, car_park_id, entry_time, status, created_at, updated_at)
            VALUES
                (?, ?, ?, 'inside', ?, ?)
            """,
            (plate, self.car_park_id, now, now, now),
        )
        self.conn.commit()
        print(f"[DB] Registered entry for plate={plate}, car_park_id={self.car_park_id}")

    def complete_exit(self, plate: str) -> None:
        """Mark the most recent 'inside' session for this plate as completed."""
        now = self._now_iso()
        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE parking_sessions
            SET exit_time = ?, status = 'completed', updated_at = ?
            WHERE id = (
                SELECT id FROM parking_sessions
                WHERE plate = ? AND car_park_id = ? AND status = 'inside'
                ORDER BY entry_time DESC
                LIMIT 1
            )
            """,
            (now, now, plate, self.car_park_id),
        )
        self.conn.commit()

        if cur.rowcount == 0:
            print(f"[DB] WARNING: No active session found for plate={plate} to complete.")
        else:
            print(f"[DB] Completed exit for plate={plate}, car_park_id={self.car_park_id}")

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
