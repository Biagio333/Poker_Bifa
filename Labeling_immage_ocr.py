import os
import cv2
import numpy as np
from scraper.Scren_cap_cel import OCRReader

INPUT_DIR = "./immage"
MIN_SCORE = 0.50

VALID_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")



if not os.path.isdir(INPUT_DIR):
    raise FileNotFoundError(f"Cartella non trovata: {INPUT_DIR}")

ocr = OCRReader(scale=0.4, gray=False)

files = sorted(os.listdir(INPUT_DIR))


for filename in files:
    if not filename.lower().endswith(VALID_EXTENSIONS):
            continue

    input_path = os.path.join(INPUT_DIR, filename)
    img = cv2.imread(input_path)
    
    img = cv2.resize(img, (0, 0), fx=0.4, fy=0.4)
    texts, ocr_time = ocr.run_ocr(img)

    img = ocr.draw_results(img, texts, ocr_time)


    output_path = os.path.join(INPUT_DIR, f"labeled_{filename}")
    cv2.imwrite(output_path, img)



