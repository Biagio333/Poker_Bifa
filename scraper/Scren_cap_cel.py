import subprocess
import numpy as np
import cv2
import time
import threading
from rapidocr_onnxruntime import RapidOCR


class OCRReader:
    def __init__(self, scale=0.5, gray=False, min_score=0.5):
        self.scale = scale
        self.gray = gray
        self.min_score = min_score
        self.engine = RapidOCR()

        self.running = False
        self.thread = None
        self.lock = threading.Lock()

        self.last_full_frame = None
        self.last_frame = None
        self.frame_id = 0

    def _grab_loop(self):
        while self.running:
            try:
                result = subprocess.run(
                    ["adb", "exec-out", "screencap", "-p"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                if result.returncode != 0:
                    err = result.stderr.decode(errors="ignore").strip()
                    if err:
                        print("ADB error:", err)
                    time.sleep(0.05)
                    continue

                if not result.stdout:
                    time.sleep(0.02)
                    continue

                data = result.stdout.replace(b"\r\r\n", b"\n")
                img_full = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)

                if img_full is None:
                    time.sleep(0.02)
                    continue

                img = img_full

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

                with self.lock:
                    self.last_full_frame = img_full
                    self.last_frame = img
                    self.frame_id += 1

            except Exception as e:
                print("Screenshot thread error:", e)
                time.sleep(0.1)

    def start_capture(self):
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._grab_loop, daemon=True)
        self.thread.start()

    def stop_capture(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1.0)
            self.thread = None

    def get_latest_frame(self):
        with self.lock:
            if self.last_frame is None:
                return None, None, -1
            return self.last_full_frame.copy(), self.last_frame.copy(), self.frame_id

    def fast_screenshot(self):
        _, img, _ = self.get_latest_frame()
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
        out = img.copy()

        for item in texts:
            box = item["box"]
            text = item["text"]
            score = item["score"]

            pts = np.array(box, dtype=np.int32)
            cv2.polylines(out, [pts], True, (0, 255, 0), 2)

            x, y = pts[0]

            cv2.putText(
                out,
                f"{text} {score:.2f}",
                (x, max(20, y - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
                cv2.LINE_AA
            )

        cv2.putText(
            out,
            f"OCR {ocr_time:.3f}s",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

        return out