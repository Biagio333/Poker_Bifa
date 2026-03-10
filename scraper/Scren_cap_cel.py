import subprocess
import numpy as np
import cv2
import time
from rapidocr_onnxruntime import RapidOCR



class OCRReader:

    def __init__(self, scale=0.5, gray=False, min_score=0.5):
        self.scale = scale
        self.gray = gray
        self.min_score = min_score
        self.engine = RapidOCR()

    def fast_screenshot(self):
        result = subprocess.run(
            ["adb", "exec-out", "screencap", "-p"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        if result.returncode != 0:
            print("ADB error:", result.stderr.decode(errors="ignore"))
            return None

        if not result.stdout:
            print("No screenshot data received.")
            return None

        data = result.stdout

        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            print("Failed to decode screenshot.")
            return None

        if self.scale != 1:
            img = cv2.resize(
                img,
                None,
                fx=self.scale,
                fy=self.scale,
                interpolation=cv2.INTER_AREA
            )

        if self.gray:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        return img

    def run_ocr(self, img):

        t0 = time.perf_counter()

        result, elapse = self.engine(img)

        t1 = time.perf_counter()

        if elapse is None:
            ocr_time = t1 - t0
        elif isinstance(elapse, list):
            ocr_time = sum(elapse)
        else:
            ocr_time = float(elapse)

        texts = []

        if result:
            for box, text, score in result:

                if score < self.min_score:
                    continue

                texts.append({
                    "text": text,
                    "score": score,
                    "box": box
                })

        return texts, ocr_time

    def draw_results(self, img, texts, ocr_time):

        for item in texts:

            box = item["box"]
            text = item["text"]
            score = item["score"]

            pts = np.array(box, dtype=np.int32)

            cv2.polylines(img, [pts], True, (0, 255, 0), 2)

            x, y = pts[0]

            cv2.putText(
                img,
                f"{text} {score:.2f}",
                (x, max(20, y - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
                cv2.LINE_AA
            )

        cv2.putText(
            img,
            f"OCR {ocr_time:.3f}s",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

        return img