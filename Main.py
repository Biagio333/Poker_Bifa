import cv2
from scraper.Scren_cap_cel import  OCRReader
from scraper.roi_map import ROIMap
from scraper.table_reader import TableReader
from scraper.ocr_utils import list_images
from scraper.Image_search import image_search
from poker.equity_calculator import PokerEquityCalculator
from poker.debug_mjpeg import MJPEGDebugServer
from poker.table import Table
import time
from enum import Enum
import subprocess
import random

class SCR_TYPE(Enum):
    ADB = 0
    SCRCPY = 1
    IMMAGE_SAVED = 2

SCRENSHOT_TYPE = SCR_TYPE.ADB


SCRCPY_CMD = [
    "scrcpy",
    "--no-display",
    "--no-control",
    "--v4l2-sink=/dev/video0",
    "--max-size", "960",
    "--max-fps", "1"
]

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
        ocr = OCRReader(scale=0.4, gray=False, min_score=0.5)
        ocr.start_capture()

    if SCRENSHOT_TYPE == SCR_TYPE.IMMAGE_SAVED:
        ocr = OCRReader(scale=0.4, gray=False, min_score=0.5)


    reader = TableReader(roi_map, min_score=0.5)

    table = Table(max_players=6, hero_seat=0)

    count = 0
    last_id = -1
    while True:

        t0 = time.time()

        if SCRENSHOT_TYPE == SCR_TYPE.IMMAGE_SAVED:
            list_img = list_images()
            count += 1
            if count >= len(list_img):
                count = 0
            print (f"Processing image: {list_img[count]}")
            img = cv2.imread(list_img[count])
            img = cv2.resize(img, (0, 0), fx=0.4, fy=0.4)

        if SCRENSHOT_TYPE == SCR_TYPE.ADB:
            img = ocr.fast_screenshot()
            frame_full, img, frame_id = ocr.get_latest_frame()
            # nessun frame ancora
            if img is None:
                time.sleep(0.1)
                continue

            # stesso frame di prima → aspetta
            if frame_id == last_id:
                time.sleep(0.1)
                continue
            last_id = frame_id

        if SCRENSHOT_TYPE == SCR_TYPE.SCRCPY:
            ris, img = cap.read()
            if not ris:
                continue
            img = cv2.resize(img, None, fx=0.4, fy=0.4)


        if img is None:
            print("Screenshot non riuscito")
            return

        ocr_results, ocr_time = ocr.run_ocr(img)

        # Cerca le carte sul tavolo
        carte_trovate = img_search.find_table_cards(img)
        print(f"Carte sul tavolo: {carte_trovate}")

        # Cerca le carte hero
        carte_hero = img_search.find_hero_cards(img)
        print(f"Carte hero: {carte_hero}")

        # Cerca il dealer button
        dealer = img_search.find_dealer_button(img,threshold=0.7)
        #print(f"Dealer button seat: {dealer}")

        # Cerca carte coperte per identificare giocatori attivi nella mano
        # Per testare diverse soglie, decommenta la riga sotto:
        # img_search.test_covered_cards_threshold(img)
        
        active_seats = img_search.find_covered_cards(img, threshold=0.8)
        print(f"Giocatori con carte coperte (in mano): {active_seats}")


        # Calcola le posizioni dei giocatori
        posizioni = img_search.get_player_positions(dealer)
        

        
        # Crea un dizionario inverso per lookup veloce
        seat_to_pos = {seat: pos for pos, seat in posizioni.items()}

        #print(f"OCR time: {ocr_time:.3f}s")
        reader.table_reset(table)
        reader.populate_table(table, ocr_results)


        img = ocr.draw_results(img, ocr_results, ocr_time)

        #server.update_frame(img)

        print("\nGiocatori:")
        print("Seat | Name           | Stack  | Position | Status")
        print("-----|----------------|--------|----------|--------")
        
        # Identifica giocatori attivi (da carte coperte) e hero
        hero_seat = None
        
        for p in table.players:
            pos_name = seat_to_pos.get(p.seat, "???") if p.seat is not None else "???"
            name_str = p.name[:14] if p.name else "???"
            stack_str = f"{p.stack:6.2f}" if p.stack is not None else "  ???"
            seat_str = p.seat if p.seat is not None else "?"
            
            # Determina status basato su carte coperte
            status = ""
            is_active = p.seat in active_seats if p.seat is not None else False
            
                            # Log specifico per seat 0
            if p.seat == 0 and        len(carte_hero) == 2 :
                    is_active = True
            else:
                    status = "FOLDED"

            if is_active:
                status = "IN HAND"
                
                    
            print(f"{seat_str:4} | {name_str:14} | {stack_str} | {pos_name:8} | {status}")


        elapsed = time.time() - t0
        print(f"Elapsed time: {elapsed:.3f}s\n")

if __name__ == "__main__":
    main()


