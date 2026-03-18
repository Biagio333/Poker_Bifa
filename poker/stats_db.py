import os
import sqlite3


class PlayerStatsDB:
    DEFAULT_STATS = {
        "hands_seen": 0,
        "vpip": 0,
        "pfr": 0,
        "bet": 0,
        "raise": 0,
        "call": 0,
        "fold": 0,
    }

    def __init__(self, db_path: str):
        self.db_path = db_path
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS player_stats (
                    player_name TEXT PRIMARY KEY,
                    hands_seen INTEGER NOT NULL DEFAULT 0,
                    vpip INTEGER NOT NULL DEFAULT 0,
                    pfr INTEGER NOT NULL DEFAULT 0,
                    bet INTEGER NOT NULL DEFAULT 0,
                    raise_count INTEGER NOT NULL DEFAULT 0,
                    call INTEGER NOT NULL DEFAULT 0,
                    fold INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def load_player(self, player_name: str):
        normalized_name = (player_name or "").strip()
        if not normalized_name:
            return self.DEFAULT_STATS.copy()

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT hands_seen, vpip, pfr, bet, raise_count, call, fold
                FROM player_stats
                WHERE player_name = ?
                """,
                (normalized_name,),
            ).fetchone()

        if row is None:
            return self.DEFAULT_STATS.copy()

        return {
            "hands_seen": int(row[0]),
            "vpip": int(row[1]),
            "pfr": int(row[2]),
            "bet": int(row[3]),
            "raise": int(row[4]),
            "call": int(row[5]),
            "fold": int(row[6]),
        }

    def save_player(self, player_name: str, stats: dict):
        normalized_name = (player_name or "").strip()
        if not normalized_name:
            return

        payload = self.DEFAULT_STATS.copy()
        for key in payload:
            payload[key] = int(stats.get(key, 0))

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO player_stats (
                    player_name, hands_seen, vpip, pfr, bet, raise_count, call, fold, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(player_name) DO UPDATE SET
                    hands_seen = excluded.hands_seen,
                    vpip = excluded.vpip,
                    pfr = excluded.pfr,
                    bet = excluded.bet,
                    raise_count = excluded.raise_count,
                    call = excluded.call,
                    fold = excluded.fold,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    normalized_name,
                    payload["hands_seen"],
                    payload["vpip"],
                    payload["pfr"],
                    payload["bet"],
                    payload["raise"],
                    payload["call"],
                    payload["fold"],
                ),
            )
