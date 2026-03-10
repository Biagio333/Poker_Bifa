import cv2
from scraper.Scren_cap_cel import  OCRReader
from scraper.roi_map import ROIMap
from scraper.table_reader import TableReader
from scraper.ocr_utils import list_images
from poker.table import Table
from poker.debug_mjpeg import MJPEGDebugServer
import time

SCRENSHOT_FROM_CARTELLA_IMMAGE = True

def main():
    #per debug: mostra il video con i risultati OCR disegnati sopra
    server = MJPEGDebugServer(host="127.0.0.1", port=5000, jpeg_quality=80)
    server.start()

    roi_map = ROIMap("data/Poker_star.json")
    roi_map.load()

    ocr = OCRReader(min_score=0.5)
    reader = TableReader(roi_map, min_score=0.5)

    table = Table(max_players=6, hero_seat=0)

    count = 0
    while True:
        t0 = time.time()
        if SCRENSHOT_FROM_CARTELLA_IMMAGE:
            list_img = list_images()
            count += 1
            if count >= len(list_img):
                count = 0
            print (f"Processing image: {list_img[count]}")
            img = cv2.imread(list_img[count])
            img = cv2.resize(img, (0, 0), fx=0.4, fy=0.4)
        else:
            img = ocr.fast_screenshot(scale=0.4, gray=False)


        if img is None:
            print("Screenshot non riuscito")
            return

        ocr_results, ocr_time = ocr.run_ocr(img)

        #print(f"OCR time: {ocr_time:.3f}s")
        reader.table_reset(table)
        reader.populate_table(table, ocr_results)


        img = ocr.draw_results(img, ocr_results, ocr_time)

        server.update_frame(img)

        for p in table.players:
            print(f"seat={p.seat} name={p.name} stack={p.stack}")

        print("pot =", table.pot)

        elapsed = time.time() - t0
        print(f"Elapsed time: {elapsed:.3f}s\n")

if __name__ == "__main__":
    main()


