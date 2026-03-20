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
        "check": 0,
        "fold": 0,
        "bet_flop": 0,
        "bet_turn": 0,
        "bet_river": 0,
        "raise_flop": 0,
        "raise_turn": 0,
        "raise_river": 0,
        "call_flop": 0,
        "call_turn": 0,
        "call_river": 0,
        "check_flop": 0,
        "check_turn": 0,
        "check_river": 0,
        "fold_flop": 0,
        "fold_turn": 0,
        "fold_river": 0,
        "three_bet_count": 0,
        "three_bet_opp": 0,
        "fold_to_cbet_count": 0,
        "fold_to_cbet_opp": 0,
        "fold_to_raise_count": 0,
        "fold_to_raise_opp": 0,
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
                    check_count INTEGER NOT NULL DEFAULT 0,
                    fold INTEGER NOT NULL DEFAULT 0,
                    bet_flop INTEGER NOT NULL DEFAULT 0,
                    bet_turn INTEGER NOT NULL DEFAULT 0,
                    bet_river INTEGER NOT NULL DEFAULT 0,
                    raise_flop INTEGER NOT NULL DEFAULT 0,
                    raise_turn INTEGER NOT NULL DEFAULT 0,
                    raise_river INTEGER NOT NULL DEFAULT 0,
                    call_flop INTEGER NOT NULL DEFAULT 0,
                    call_turn INTEGER NOT NULL DEFAULT 0,
                    call_river INTEGER NOT NULL DEFAULT 0,
                    check_flop INTEGER NOT NULL DEFAULT 0,
                    check_turn INTEGER NOT NULL DEFAULT 0,
                    check_river INTEGER NOT NULL DEFAULT 0,
                    fold_flop INTEGER NOT NULL DEFAULT 0,
                    fold_turn INTEGER NOT NULL DEFAULT 0,
                    fold_river INTEGER NOT NULL DEFAULT 0,
                    three_bet_count INTEGER NOT NULL DEFAULT 0,
                    three_bet_opp INTEGER NOT NULL DEFAULT 0,
                    fold_to_cbet_count INTEGER NOT NULL DEFAULT 0,
                    fold_to_cbet_opp INTEGER NOT NULL DEFAULT 0,
                    fold_to_raise_count INTEGER NOT NULL DEFAULT 0,
                    fold_to_raise_opp INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            existing_columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(player_stats)").fetchall()
            }
            if "check_count" not in existing_columns:
                conn.execute(
                    "ALTER TABLE player_stats ADD COLUMN check_count INTEGER NOT NULL DEFAULT 0"
                )
            for column_name in (
                "bet_flop",
                "bet_turn",
                "bet_river",
                "raise_flop",
                "raise_turn",
                "raise_river",
                "call_flop",
                "call_turn",
                "call_river",
                "check_flop",
                "check_turn",
                "check_river",
                "fold_flop",
                "fold_turn",
                "fold_river",
                "three_bet_count",
                "three_bet_opp",
                "fold_to_cbet_count",
                "fold_to_cbet_opp",
            ):
                if column_name not in existing_columns:
                    conn.execute(
                        f"ALTER TABLE player_stats ADD COLUMN {column_name} INTEGER NOT NULL DEFAULT 0"
                    )
            if "fold_to_raise_count" not in existing_columns:
                conn.execute(
                    "ALTER TABLE player_stats ADD COLUMN fold_to_raise_count INTEGER NOT NULL DEFAULT 0"
                )
            if "fold_to_raise_opp" not in existing_columns:
                conn.execute(
                    "ALTER TABLE player_stats ADD COLUMN fold_to_raise_opp INTEGER NOT NULL DEFAULT 0"
                )

    def load_player(self, player_name: str):
        normalized_name = (player_name or "").strip()
        if not normalized_name:
            return self.DEFAULT_STATS.copy()

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT hands_seen, vpip, pfr, bet, raise_count, call, check_count, fold,
                       bet_flop, bet_turn, bet_river,
                       raise_flop, raise_turn, raise_river,
                       call_flop, call_turn, call_river,
                       check_flop, check_turn, check_river,
                       fold_flop, fold_turn, fold_river,
                       three_bet_count, three_bet_opp,
                       fold_to_cbet_count, fold_to_cbet_opp,
                       fold_to_raise_count, fold_to_raise_opp
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
            "check": int(row[6]),
            "fold": int(row[7]),
            "bet_flop": int(row[8]),
            "bet_turn": int(row[9]),
            "bet_river": int(row[10]),
            "raise_flop": int(row[11]),
            "raise_turn": int(row[12]),
            "raise_river": int(row[13]),
            "call_flop": int(row[14]),
            "call_turn": int(row[15]),
            "call_river": int(row[16]),
            "check_flop": int(row[17]),
            "check_turn": int(row[18]),
            "check_river": int(row[19]),
            "fold_flop": int(row[20]),
            "fold_turn": int(row[21]),
            "fold_river": int(row[22]),
            "three_bet_count": int(row[23]),
            "three_bet_opp": int(row[24]),
            "fold_to_cbet_count": int(row[25]),
            "fold_to_cbet_opp": int(row[26]),
            "fold_to_raise_count": int(row[27]),
            "fold_to_raise_opp": int(row[28]),
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
                    player_name, hands_seen, vpip, pfr, bet, raise_count, call, check_count, fold,
                    bet_flop, bet_turn, bet_river,
                    raise_flop, raise_turn, raise_river,
                    call_flop, call_turn, call_river,
                    check_flop, check_turn, check_river,
                    fold_flop, fold_turn, fold_river,
                    three_bet_count, three_bet_opp,
                    fold_to_cbet_count, fold_to_cbet_opp,
                    fold_to_raise_count, fold_to_raise_opp, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(player_name) DO UPDATE SET
                    hands_seen = excluded.hands_seen,
                    vpip = excluded.vpip,
                    pfr = excluded.pfr,
                    bet = excluded.bet,
                    raise_count = excluded.raise_count,
                    call = excluded.call,
                    check_count = excluded.check_count,
                    fold = excluded.fold,
                    bet_flop = excluded.bet_flop,
                    bet_turn = excluded.bet_turn,
                    bet_river = excluded.bet_river,
                    raise_flop = excluded.raise_flop,
                    raise_turn = excluded.raise_turn,
                    raise_river = excluded.raise_river,
                    call_flop = excluded.call_flop,
                    call_turn = excluded.call_turn,
                    call_river = excluded.call_river,
                    check_flop = excluded.check_flop,
                    check_turn = excluded.check_turn,
                    check_river = excluded.check_river,
                    fold_flop = excluded.fold_flop,
                    fold_turn = excluded.fold_turn,
                    fold_river = excluded.fold_river,
                    three_bet_count = excluded.three_bet_count,
                    three_bet_opp = excluded.three_bet_opp,
                    fold_to_cbet_count = excluded.fold_to_cbet_count,
                    fold_to_cbet_opp = excluded.fold_to_cbet_opp,
                    fold_to_raise_count = excluded.fold_to_raise_count,
                    fold_to_raise_opp = excluded.fold_to_raise_opp,
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
                    payload["check"],
                    payload["fold"],
                    payload["bet_flop"],
                    payload["bet_turn"],
                    payload["bet_river"],
                    payload["raise_flop"],
                    payload["raise_turn"],
                    payload["raise_river"],
                    payload["call_flop"],
                    payload["call_turn"],
                    payload["call_river"],
                    payload["check_flop"],
                    payload["check_turn"],
                    payload["check_river"],
                    payload["fold_flop"],
                    payload["fold_turn"],
                    payload["fold_river"],
                    payload["three_bet_count"],
                    payload["three_bet_opp"],
                    payload["fold_to_cbet_count"],
                    payload["fold_to_cbet_opp"],
                    payload["fold_to_raise_count"],
                    payload["fold_to_raise_opp"],
                ),
            )

    def clear_all_stats(self) -> int:
        with self._connect() as conn:
            deleted_rows = conn.execute("SELECT COUNT(*) FROM player_stats").fetchone()[0]
            conn.execute("DELETE FROM player_stats")
        return int(deleted_rows)
