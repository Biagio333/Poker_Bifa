# ollama run hf.co/mradermacher/poker-reasoning-14b-GGUF:Q3_K_S
#nc -u -l 9000
#nc -u -l 9001 | jq -C


import cv2
from scraper.Scren_cap_cel import  OCRReader
from scraper.roi_map import ROIMap
from scraper.table_reader import TableReader
from scraper.ocr_utils import list_images
from scraper.Image_search import image_search
from poker.equity_calculator import PokerEquityCalculator
from poker.debug_mjpeg import MJPEGDebugServer
from poker.ollama_advisor import build_ollama_prompt, choose_action_with_ollama
from poker.table import Table
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
DISPLAY_SCALE = 0.4
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
    
    if SCRENSHOT_TYPE == SCR_TYPE.SCRCPY:
        proc = start_scrcpy()
        time.sleep(2)  # tempo per avviare lo stream
        cap = cv2.VideoCapture("/dev/video0")

    #per debug: mostra il video con i risultati OCR disegnati sopra
    server = MJPEGDebugServer(host="127.0.0.1", port=5000, jpeg_quality=80)
    server.start()

    roi_map = ROIMap("data/Poker_star.json")
    roi_map.load()

    # Inizializza image_search e carica le immagini
    img_search = image_search(roi_map, "Poker_star")
    img_search.load_images("Poker_star")

    # Inizializza equity calculator
    equity_calc = PokerEquityCalculator()

    if SCRENSHOT_TYPE == SCR_TYPE.ADB :
        ocr = OCRReader(scale=DISPLAY_SCALE, gray=False, min_score=0.5)
        ocr.start_capture()

    if SCRENSHOT_TYPE == SCR_TYPE.IMMAGE_SAVED:
        ocr = OCRReader(scale=DISPLAY_SCALE, gray=False, min_score=0.5)


    reader = TableReader(roi_map, min_score=0.5)

    table = Table(max_players=6, hero_seat=0)

    count = 0
    last_id = -1
    last_action_labels = None
    last_ollama_decision = None
    last_sent_action_labels = None
    last_pressed_action_labels = None
    wait_press_button = False
    while True:


        t0 = time.time()

        if SCRENSHOT_TYPE == SCR_TYPE.IMMAGE_SAVED:
            list_img = list_images()
            count += 1
            if count >= len(list_img):
                count = 0
            print (f"Processing image: {list_img[count]}")
            img = cv2.imread(list_img[count])
            img = cv2.resize(img, (0, 0), fx=DISPLAY_SCALE, fy=DISPLAY_SCALE)

        if SCRENSHOT_TYPE == SCR_TYPE.ADB:
            img = ocr.fast_screenshot()
            # nessun frame ancora
            if img is None:
                time.sleep(0.1)
                continue
            print("Frames nel buffer:", ocr.buffer_size())


        if SCRENSHOT_TYPE == SCR_TYPE.SCRCPY:
            ris, img = cap.read()
            if not ris:
                continue
            img = cv2.resize(img, None, fx=DISPLAY_SCALE, fy=DISPLAY_SCALE)


        if img is None:
            print("Screenshot non riuscito")
            return

        ocr_results, ocr_time = ocr.run_ocr(img)
        reader.table_reset(table)

        reader.populate_table(table, ocr_results)
        current_action_labels = tuple(
                    action.get("label", "").strip().lower()
                    for action in table.available_actions
                )

        #se ho gia preso un azione aspetto che spariscano i pulsanti per continuare
        if wait_press_button == False:

            # Cerca le carte sul tavolo
            carte_trovate = img_search.find_table_cards(img)
            carte_trovate = [card[0].upper() + card[1] for card in carte_trovate]
            print(f"Carte sul tavolo: {carte_trovate}")

            # Cerca le carte hero
            carte_hero = img_search.find_hero_cards(img)
            carte_hero = [card[0].upper() + card[1] for card in carte_hero]
            print(f"Carte hero: {carte_hero}")

            # Cerca il dealer button
            dealer = img_search.find_dealer_button(img,threshold=0.7)
            #print(f"Dealer button seat: {dealer}")

            # Cerca carte coperte per identificare giocatori attivi nella mano
            # Per testare diverse soglie, decommenta la riga sotto:
            # img_search.test_covered_cards_threshold(img)
            
            active_seats = img_search.find_covered_cards(img, threshold=0.8)
            #print(f"Giocatori con carte coperte (in mano): {active_seats}")


            # Calcola le posizioni dei giocatori
            posizioni = img_search.get_player_positions(dealer)
            

            
            # Crea un dizionario inverso per lookup veloce
            seat_to_pos = {seat: pos for pos, seat in posizioni.items()}
            hero_position = seat_to_pos.get(table.hero_seat)
            big_blind_seat = posizioni.get("BB")
            big_blind = None
            if big_blind_seat is not None:
                big_blind = table.get_player(big_blind_seat).current_bet

            #print(f"OCR time: {ocr_time:.3f}s")

            table.set_board_cards(carte_trovate)
            table.set_hero_cards(carte_hero)

            act = table.format_available_actions(DISPLAY_SCALE)


            #server.update_frame(img)

            print(f"\nMano corrente: {table.street} | Pot: {table.pot:.2f} | Board: {table.board_cards} | Hero: {table.hero_cards}")
            print(table.format_available_actions(DISPLAY_SCALE))

            print("\nGiocatori:")
            print("Seat | Name           | Stack  | Bet    | Position | Type       | Status")
            print("-----|----------------|--------|--------|----------|------------|--------")
            
            # Identifica giocatori attivi (da carte coperte) e hero
            hero_seat = None
            active_players_for_equity = []
            hero_equity = None
            
            for p in table.players:
                p.set_player_type(PLAYER_TYPES_BY_SEAT.get(p.seat, "loose"))
                pos_name = seat_to_pos.get(p.seat, "???") if p.seat is not None else "???"
                name_str = p.name[:14] if p.name else "???"
                stack_str = f"{p.stack:6.2f}" if p.stack is not None else "  ???"
                bet_str = f"{p.current_bet:6.2f}" if p.current_bet is not None else "  ???"
                seat_str = p.seat if p.seat is not None else "?"
                type_str = p.player_type[:10]
                
                # Determina status basato su carte coperte
                status = ""
                is_active = p.seat in active_seats if p.seat is not None else False
                
                                # Log specifico per seat 0
                status = "FOLDED"
                is_active = p.seat in active_seats if p.seat is not None else False

                if p.seat == table.hero_seat and len(table.hero_cards) == 2:
                    is_active = True

                if is_active:
                    status = "IN HAND"
                    active_players_for_equity.append(p)
                    if p.seat == table.hero_seat:
                        hero_seat = p.seat
                    
                        
                print(f"{seat_str:4} | {name_str:14} | {stack_str} | {bet_str} | {pos_name:8} | {type_str:10} | {status}")

            # Calcola equity dell'hero solo quando ci sono i pulsanti sul tavolo
            if len(table.hero_cards) == 2 and len(active_players_for_equity) >= 2:
                if len(table.available_actions) > 0 and len(table.hero_cards) == 2:
                    if len(active_players_for_equity) >= 2:
                        opponents = [
                            player for player in active_players_for_equity
                            if player.seat != table.hero_seat
                        ]

                        if opponents:
                            player_hands = [table.hero_cards] + [[] for _ in opponents]

                            player_types = [
                                PLAYER_TYPES_BY_SEAT.get(table.hero_seat, "loose")
                            ] + [
                                player.player_type for player in opponents
                            ]

                            equities = equity_calc.calculate_equity(
                                player_hands=player_hands,
                                board_cards=table.board_cards,
                                iterations=1000,
                                player_types=player_types,
                            )

                            hero_equity = equities[0]
                            print("Hero equity:", hero_equity)
                        else:
                            print("Nessun avversario attivo contro cui calcolare equity")           


                old_current_action_labels = current_action_labels


                if not current_action_labels:
                    last_action_labels = None
                    last_ollama_decision = None
                    last_pressed_action_labels = None
                elif current_action_labels != last_action_labels:
                    try:
                        ollama_prompt = build_ollama_prompt(
                            table,
                            hero_equity=hero_equity,
                            hero_position=hero_position,
                            big_blind=big_blind,
                        )
                        send_udp_text(ollama_prompt)

                        last_ollama_decision = choose_action_with_ollama(
                            table,
                            hero_equity=hero_equity,
                            hero_position=hero_position,
                            big_blind=big_blind,
                        )
                    except Exception as exc:
                        last_ollama_decision = {
                            "selected_action": None,
                            "reason": f"Errore Ollama: {exc}",
                            "raw_response": "",
                        }
                    last_action_labels = current_action_labels
                    last_sent_action_labels = None

                if last_ollama_decision is not None:
                    selected_action = last_ollama_decision.get("selected_action")
                    selected_label = selected_action.get("label", "") if selected_action else ""
                    selected_point = selected_action.get("click_point", {}) if selected_action else {}
                    selected_x = selected_point.get("x")
                    selected_y = selected_point.get("y")

                    if isinstance(selected_x, (int, float)) and isinstance(selected_y, (int, float)):
                        selected_x = int(round(selected_x / DISPLAY_SCALE))
                        selected_y = int(round(selected_y / DISPLAY_SCALE))

                    if selected_action and current_action_labels != last_sent_action_labels:
                        send_udp_message({
                            "type": "ollama_decision",
                            "label": selected_label,
                            "x": selected_x,
                            "y": selected_y,
                            "equity": hero_equity,
                            "reason": last_ollama_decision.get("reason", ""),
                            "street": table.street,
                            "pot": table.pot,
                            "board_cards": table.board_cards,
                            "hero_cards": table.hero_cards,
                        })
                        last_sent_action_labels = current_action_labels

                    if selected_action:
                        print(f"{RED_TEXT}Ollama decision: {selected_label} -> ({selected_x}, {selected_y}){RESET_TEXT}")

                        if (
                            SCRENSHOT_TYPE == SCR_TYPE.ADB
                            and isinstance(selected_x, int)
                            and isinstance(selected_y, int)
                            and current_action_labels != last_pressed_action_labels
                        ):
                            try:
                                adb_tap(selected_x, selected_y)
                                last_pressed_action_labels = current_action_labels
                                print(f"{RED_TEXT}ADB tap eseguito su ({selected_x}, {selected_y}){RESET_TEXT}")
                            except Exception as exc:
                                print(f"{RED_TEXT}ADB tap fallito: {exc}{RESET_TEXT}")

                        wait_press_button =True
                    else:
                        print(f"{RED_TEXT}Ollama decision: None{RESET_TEXT}")
                    print(f"{RED_TEXT}Ollama reason: {last_ollama_decision.get('reason', '')}{RESET_TEXT}")


            elapsed = time.time() - t0
            print(f"Elapsed time: {elapsed:.3f}s\n")
        else: #aspetto che venga premuto il pulsante suggerito da Ollama
            ratio = SequenceMatcher(None, old_current_action_labels, current_action_labels).ratio()
            if ratio < 0.8:
                wait_press_button = False
                last_pressed_action_labels = None

if __name__ == "__main__":
    main()
