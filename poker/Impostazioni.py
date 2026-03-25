from enum import Enum


class SCR_TYPE(Enum):
    ADB = 0
    SCRCPY = 1
    IMMAGE_SAVED = 2


SCRENSHOT_TYPE = SCR_TYPE.ADB
AUTO_PRESS_BUTTON = True 
SAVE_SCREENSHOT = False
SAVE_SCREENSHOT_DIR = "immage"
DEBUG_START_FRAME_NUMBER = 0
DISPLAY_SCALE = 0.8
DISPLAY_PREVIEW = False
PLAYER_STATS_DB_PATH = "data/player_stats.db"
RED_TEXT = "\033[91m"
RESET_TEXT = "\033[0m"
OCR_ENGINE = "rapidocr"  # "rapidocr" oppure "paddleocr"

table_name = "Poker_star_oppo_1080x2400"
HALTEZZA_FOLD = 36  # oppo
#HALTEZZA_FOLD = 30  # A53

game_type_set = "tournament"  # "tournament"  "cash"

play_style_set = "aggressive"    #"mixed"   "conservative" "aggressive"

if game_type_set == "tournament":
    IS_TORNEY = True
else:
    IS_TORNEY = False
