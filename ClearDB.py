from pathlib import Path

from poker.stats_db import PlayerStatsDB


DB_PATH = Path(__file__).resolve().parent / "data" / "player_stats.db"


def main():
    stats_db = PlayerStatsDB(str(DB_PATH))
    deleted_rows = stats_db.clear_all_stats()
    print(f"Statistiche cancellate. Record rimossi: {deleted_rows}")


if __name__ == "__main__":
    main()
