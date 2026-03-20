# ollama run hf.co/mradermacher/poker-reasoning-14b-GGUF:Q3_K_S
#nc -u -l 9000
#nc -u -l 9001 | jq -C


import cv2
import os
from scraper.Scren_cap_cel import  OCRReader
from scraper.roi_map import ROIMap
from scraper.table_reader import TableReader
from scraper.ocr_utils import list_images
from scraper.Image_search import image_search
from poker.equity_calculator import PokerEquityCalculator
from poker.debug_mjpeg import MJPEGDebugServer
from poker.rule_based_advisor import choose_action_with_rules
from poker.table import Table
from poker.stats_db import PlayerStatsDB
from poker.udp_sender import send_udp_message, send_udp_text
import time
from enum import Enum
import subprocess
import random
from difflib import SequenceMatcher

class SCR_TYPE(Enum):
    ADB = 0
    SCRCPY = 1
    IMMAGE_SAVED = 2

SCRENSHOT_TYPE = SCR_TYPE.ADB
SAVE_SCREENSHOT = False
SAVE_SCREENSHOT_DIR = "immage"
DISPLAY_SCALE = 0.8
DISPLAY_PREVIEW = False
PLAYER_STATS_DB_PATH = "data/player_stats.db"
RED_TEXT = "\033[91m"
RESET_TEXT = "\033[0m"


SCRCPY_CMD = [
    "scrcpy",
    "--no-display",
    "--no-control",
    "--v4l2-sink=/dev/video0",
    "--max-size", "960",
    "--max-fps", "1"
]


def adb_tap(x, y):
    result = subprocess.run(
        ["adb", "shell", "input", "tap", str(int(x)), str(int(y))],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Comando adb tap fallito.")

    return True

def start_scrcpy():
    return subprocess.Popen(
        SCRCPY_CMD,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def _generate_random_hand(exclude_cards):
    """Genera una mano random escludendo le carte già note"""
    deck = [r+s for r in '23456789TJQKA' for s in 'cdhs']
    available = [card for card in deck if card not in exclude_cards]
    random.shuffle(available)
    return available[:2]


PLAYER_TYPES_BY_SEAT = {
    0: "aggressive",
    1: "aggressive",
    2: "aggressive",
    3: "aggressive",
    4: "aggressive",
    5: "aggressive",
}

def main():
    saved_screenshot_count = 0
    preview_window = "Poker Bifa"

    if SCRENSHOT_TYPE == SCR_TYPE.ADB and SAVE_SCREENSHOT:
        os.makedirs(SAVE_SCREENSHOT_DIR, exist_ok=True)

    if DISPLAY_PREVIEW:
        cv2.namedWindow(preview_window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(preview_window, 960, 540)

    
    if SCRENSHOT_TYPE == SCR_TYPE.SCRCPY:
        proc = start_scrcpy()
        time.sleep(2)  # tempo per avviare lo stream
        cap = cv2.VideoCapture("/dev/video0")

    #per debug: mostra il video con i risultati OCR disegnati sopra
    server = MJPEGDebugServer(host="127.0.0.1", port=5000, jpeg_quality=80)
    server.start()

    roi_map = ROIMap("data/Poker_star.json")
    roi_map.load(DISPLAY_SCALE/0.4)  # le ROI sono state disegnate su screenshot al 40%, quindi scalano di conseguenza

    # Inizializza image_search e carica le immagini
    img_search = image_search(roi_map, "Poker_star", scale_factor=DISPLAY_SCALE)
    img_search.load_images("Poker_star")  # le immagini sono state disegnate su screenshot al 40%, quindi scalano di conseguenza

    # Inizializza equity calculator
    equity_calc = PokerEquityCalculator()

    if SCRENSHOT_TYPE == SCR_TYPE.ADB :
        ocr = OCRReader(scale=DISPLAY_SCALE, gray=False, min_score=0.5)
        ocr.start_capture()

    if SCRENSHOT_TYPE == SCR_TYPE.IMMAGE_SAVED:
        ocr = OCRReader(scale=DISPLAY_SCALE, gray=False, min_score=0.5)

    if SCRENSHOT_TYPE == SCR_TYPE.SCRCPY:
        ocr = OCRReader(scale=DISPLAY_SCALE, gray=False, min_score=0.5)


    reader = TableReader(roi_map, min_score=0.5)

    table = Table(max_players=6, hero_seat=0)
    stats_db = PlayerStatsDB(PLAYER_STATS_DB_PATH)

    count = -1
    last_id = -1
    last_action_labels = None
    last_ollama_decision = None
    last_sent_action_labels = None
    last_pressed_action_labels = None
    old_current_action_labels = None
    wait_press_button = False
    street_for_ocr_actions = "preflop"

    table_hero_cards_old = []
    while True:


        t0 = time.time()

        if SCRENSHOT_TYPE == SCR_TYPE.IMMAGE_SAVED:
            list_img = list_images()
            if not list_img:
                print(f"Nessuna immagine trovata in '{SAVE_SCREENSHOT_DIR}'")
                time.sleep(0.5)
                continue
            count = (count + 1) % len(list_img)
            print(f"Processing image: {list_img[count]}")
            img = cv2.imread(list_img[count])
            img = cv2.resize(img, (0, 0), fx=DISPLAY_SCALE, fy=DISPLAY_SCALE)

        if SCRENSHOT_TYPE == SCR_TYPE.ADB:
            img_full, img, _ = ocr.get_next_frame()
            # nessun frame ancora
            if img is None:
                time.sleep(0.1)
                continue
            print("Frames nel buffer:", ocr.buffer_size())

            if SAVE_SCREENSHOT and img_full is not None:
                ts = int(time.time() * 1000)
                file_name = f"adb_{ts}_{saved_screenshot_count:06d}.png"
                file_path = os.path.join(SAVE_SCREENSHOT_DIR, file_name)
                if cv2.imwrite(file_path, img_full):
                    saved_screenshot_count += 1
                    print(f"Screenshot salvato: {file_path}")
                else:
                    print(f"Errore salvataggio screenshot: {file_path}")


        if SCRENSHOT_TYPE == SCR_TYPE.SCRCPY:
            ris, img = cap.read()
            if not ris:
                continue
            img = cv2.resize(img, None, fx=DISPLAY_SCALE, fy=DISPLAY_SCALE)


        if img is None:
            print("Screenshot non riuscito")
            return

        if DISPLAY_PREVIEW:
            cv2.imshow(preview_window, img)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

        img_for_ocr = img_search.apply_ocr_mask(img)

        t0 = time.time()
        ocr_results, ocr_time = ocr.run_ocr(img_for_ocr)
        elapsed_ocr = time.time() - t0


        img_populated = ocr.draw_results (img, ocr_results, 0)  # disegna solo i risultati OCR senza testo per debug
        server.update_frame(img_populated)
        #reader.table_reset(table)

        # Cerca le carte sul tavolo
        carte_trovate = img_search.find_table_cards(img)
        carte_trovate = [card[0].upper() + card[1] for card in carte_trovate]
        print(f"Carte sul tavolo: {carte_trovate}")

        table.set_board_cards(carte_trovate)
        street_for_ocr_actions = table.street

      
        if len( table.hero_cards ) == 2:
            if table.hero_cards != table_hero_cards_old:
                table_hero_cards_old = list(table.hero_cards)
                for player in table.players:
                    player.request_reset_hand = False
                    for street in player.actions_by_street:
                        if street != "preflop":  # voglio mantenere le azioni OCR del preflop anche quando cambia la mano, perche a volte non riesce a leggerle bene e mi serve un po di memoria
                            player.actions_by_street[street].clear()
                reader.table_reset(table) 

        reader.populate_table(table, ocr_results)

        for player in table.players:
            loaded_profile_name = player.get_stats_profile_name()
            if player.has_dirty_stats() and loaded_profile_name:
                stats_db.save_player(loaded_profile_name, player.export_stats())
                if loaded_profile_name == (player.name or "").strip():
                    player.mark_stats_saved()

            if player.needs_stats_load():
                stats_db_stats = stats_db.load_player(player.name)
                player.load_stats(stats_db_stats, (player.name or "").strip())

            if player.has_dirty_stats() and player.get_stats_profile_name():
                stats_db.save_player(player.get_stats_profile_name(), player.export_stats())
                player.mark_stats_saved()

        current_action_labels = tuple(
                    action.get("label", "").strip().lower()
                    for action in table.available_actions
                )
        dealer = img_search.find_dealer_button(img,threshold=0.6)
        posizioni = img_search.get_player_positions(dealer)
        seat_to_pos = {seat: pos for pos, seat in posizioni.items()}

        print(table.format_players_stats(seat_to_pos))

        elapsed = time.time() - t0
        print(f"Elapsed time: {elapsed:.3f}         {elapsed_ocr:.3f} s\n")

        #se ho gia preso un azione aspetto che spariscano i pulsanti per continuare
        if wait_press_button == False:



            # Cerca le carte hero
            carte_hero = img_search.find_hero_cards(img)
            carte_hero = [card[0].upper() + card[1] for card in carte_hero]
            print(f"Carte hero: {carte_hero}")

            # Cerca carte coperte per identificare giocatori attivi nella mano
            # Per testare diverse soglie, decommenta la riga sotto:
            # img_search.test_covered_cards_threshold(img)
            
            active_seats = img_search.find_covered_cards(img, threshold=0.8)
            #print(f"Giocatori con carte coperte (in mano): {active_seats}")

            # Crea un dizionario inverso per lookup veloce
            hero_position = seat_to_pos.get(table.hero_seat)
            big_blind_seat = posizioni.get("BB")
            big_blind = None
            if big_blind_seat is not None:
                big_blind = table.get_player(big_blind_seat).current_bet

            #print(f"OCR time: {ocr_time:.3f}s")

            table.set_hero_cards(carte_hero)

            print(f"\nMano corrente: {table.street} | Pot: {table.pot:.2f} | Board: {table.board_cards} | Hero: {table.hero_cards}")
            act, select_amount_buttons = table.format_available_actions(DISPLAY_SCALE)

            if table.available_actions:
                print,f"Azioni disponibili: {act}"
                if select_amount_buttons:
                    print(f"Pulsanti di selezione importo disponibili: {[btn.get('label', '') for btn in select_amount_buttons]}")

            h=0
            if len (table.available_actions)==0:
                old_current_action_labels =None
            else:
                h=table.available_actions[0]['ocr_rect']['h']
                if h<36: # se l'altezza del rettangolo OCR è troppo piccola, probabilmente è un errore di lettura e non devo resettare la memoria delle azioni disponibili
                    old_current_action_labels =None
            
            if h>36 and old_current_action_labels== None:

                    equity_result = equity_calc.calculate_table_equity(
                        table,
                        seat_to_position=seat_to_pos,
                        active_seats=active_seats,
                        iterations=1000,
                    )
                    hero_equity = equity_result["hero_equity"]
                    if hero_equity is not None:
                        print("Hero equity:", hero_equity)

                    old_current_action_labels = current_action_labels


                    if not current_action_labels:
                        last_action_labels = None
                        last_ollama_decision = None
                        last_pressed_action_labels = None
                    else :
                        try:
                            last_ollama_decision = choose_action_with_rules(
                                table,
                                hero_equity=hero_equity,
                                hero_position=hero_position,
                                big_blind=big_blind,
                                seat_to_position=seat_to_pos,
                            )
                        except Exception as exc:
                            last_ollama_decision = {
                                "selected_action": None,
                                "reason": f"Errore advisor rules: {exc}",
                                "debug": {},
                                "table_state": {},
                            }


                    if last_ollama_decision is not None:
                        selected_action = last_ollama_decision.get("selected_action")
                        selected_label = selected_action.get("label", "") if selected_action else ""
                        selected_point = selected_action.get("click_point", {}) if selected_action else {}
                        selected_x = selected_point.get("x")
                        selected_y = selected_point.get("y")

                        if isinstance(selected_x, (int, float)) and isinstance(selected_y, (int, float)):
                            selected_x = int(round(selected_x/DISPLAY_SCALE)) 
                            selected_y = int(round(selected_y/DISPLAY_SCALE))


                        send_udp_message({
                            "type": "rule_decision",
                            "label": selected_label or "None",
                            "x": selected_x,
                            "y": selected_y,
                            "equity": hero_equity,
                            "reason": last_ollama_decision.get("reason", ""),
                            "debug": last_ollama_decision.get("debug", {}),
                            "street": table.street,
                            "pot": table.pot,
                            "board_cards": table.board_cards,
                            "hero_cards": table.hero_cards,
                        })
                        

                        if selected_action:
                            print(f"{RED_TEXT}Rule decision: {selected_label} -> ({selected_x}, {selected_y}){RESET_TEXT}")

                            if (
                                SCRENSHOT_TYPE == SCR_TYPE.ADB
                                and isinstance(selected_x, int)
                                and isinstance(selected_y, int)
                                and current_action_labels != last_pressed_action_labels
                            ):
                                try:
                                    # Esegue davvero il click ADB sull'azione selezionata.
                                    adb_tap(selected_x, selected_y)
                                    last_pressed_action_labels = current_action_labels
                                    print(f"{RED_TEXT}ADB tap eseguito su ({selected_x}, {selected_y}){RESET_TEXT}")
                                except Exception as exc:
                                    print(f"{RED_TEXT}ADB tap fallito: {exc}{RESET_TEXT}")

                            wait_press_button = True
                        else:
                            print(f"{RED_TEXT}Rule decision: None{RESET_TEXT}")

                        print(f"{RED_TEXT}Rule reason: {last_ollama_decision.get('reason', '')}{RESET_TEXT}")
                        print(f"{RED_TEXT}Rule debug: {last_ollama_decision.get('debug', {})}{RESET_TEXT}")



                    elapsed = time.time() - t0
                    print(f"Elapsed time: {elapsed:.3f}s\n")
                    elapsed = time.time() - t0
                    print(f"Elapsed time: {elapsed:.3f}         {elapsed_ocr:.3f} s\n")
        else: #aspetto che venga premuto il pulsante suggerito da Ollama
            ratio = SequenceMatcher(None, old_current_action_labels, current_action_labels).ratio()
            if ratio < 0.8:
                wait_press_button = False
                last_pressed_action_labels = None

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
