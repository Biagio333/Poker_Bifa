import os

# PaddleOCR può fare controlli remoti e inizializzare plugin Qt non adatti ad ambienti headless.
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import subprocess
import inspect
import numpy as np
import cv2
import time
import threading
from collections import deque

from poker import Impostazioni as cfg


class OCRReader:
    def __init__(self, scale=0.5, gray=False, min_score=0.5, buffer_size=5, engine_name=None):
        self.scale = scale
        self.gray = gray
        self.min_score = min_score
        self.engine_name = (engine_name or cfg.OCR_ENGINE).strip().lower()
        self.engine = self._create_engine()

        self.running = False
        self.thread = None
        self.lock = threading.Lock()

        # buffer circolare dei frame
        self.frames = deque(maxlen=buffer_size)

        self.frame_id = 0

    def _is_paddle_gpu_available(self):
        try:
            import paddle
        except ImportError:
            return False

        try:
            return bool(
                paddle.device.is_compiled_with_cuda()
                and paddle.device.cuda.device_count() > 0
            )
        except Exception:
            return False

    def _build_paddleocr_kwargs(self, paddle_ocr_class):
        use_gpu = self._is_paddle_gpu_available()
        kwargs = {}

        try:
            parameters = inspect.signature(paddle_ocr_class.__init__).parameters
        except (TypeError, ValueError):
            parameters = {}

        if "use_angle_cls" in parameters:
            kwargs["use_angle_cls"] = False
        if "lang" in parameters:
            kwargs["lang"] = "en"
        if "use_gpu" in parameters:
            kwargs["use_gpu"] = use_gpu
        elif "device" in parameters:
            kwargs["device"] = "gpu" if use_gpu else "cpu"

        backend_name = "CUDA" if use_gpu else "CPU"
        print(f"PaddleOCR avviato con {backend_name}")
        return kwargs

    def _create_engine(self):
        if self.engine_name == "rapidocr":
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError as exc:
                raise RuntimeError(
                    "RapidOCR non installato. Installa il pacchetto 'rapidocr-onnxruntime' oppure cambia OCR_ENGINE."
                ) from exc
            return RapidOCR()

        if self.engine_name == "paddleocr":
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:
                raise RuntimeError(
                    "PaddleOCR non installato. Installa il pacchetto 'paddleocr' oppure cambia OCR_ENGINE."
                ) from exc

            kwargs = self._build_paddleocr_kwargs(PaddleOCR)
            return PaddleOCR(**kwargs)

        raise ValueError(f"OCR engine non supportato: {self.engine_name}")

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
                    time.sleep(0.2)
                    continue

                if not result.stdout:
                    time.sleep(0.2)
                    continue

                data = result.stdout.replace(b"\r\r\n", b"\n")
                img_full = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)

                if img_full is None:
                    time.sleep(0.2)
                    continue

                img = img_full

                real_scale = self.scale

                if real_scale != 1:
                    img = cv2.resize(
                        img,
                        None,
                        fx=real_scale,
                        fy=real_scale,
                        interpolation=cv2.INTER_AREA
                    )

                if self.gray:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                with self.lock:
                    self.frames.append((img_full, img, self.frame_id))
                    self.frame_id += 1

                time.sleep(0.5)

            except Exception as e:
                print("Screenshot thread error:", e)
                time.sleep(0.2)

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
            if not self.frames:
                return None, None, -1

            img_full, img, fid = self.frames[-1]
            return img_full.copy(), img.copy(), fid

    def get_next_frame(self):
        with self.lock:
            if not self.frames:
                return None, None, -1

            img_full, img, fid = self.frames.popleft()
            return img_full, img, fid

    def fast_screenshot(self):
        _, img, _ = self.get_next_frame()

        return img

    def buffer_size(self):
        with self.lock:
            return len(self.frames)

    def _normalize_box(self, box):
        if box is None:
            return []

        normalized = []
        for point in box:
            if point is None or len(point) < 2:
                continue
            normalized.append([float(point[0]), float(point[1])])

        return normalized

    def _normalize_ocr_item(self, box, text, score):
        normalized_box = self._normalize_box(box)
        if len(normalized_box) < 4:
            return None

        return {
            "text": str(text).strip(),
            "score": float(score),
            "box": normalized_box,
        }

    def _run_rapidocr(self, img):
        result, elapse = self.engine(img)

        if elapse is None:
            ocr_time = 0.0
        elif isinstance(elapse, list):
            ocr_time = sum(elapse)
        else:
            ocr_time = float(elapse)

        texts = []
        if result:
            for box, text, score in result:
                normalized_item = self._normalize_ocr_item(box, text, score)
                if normalized_item is None or normalized_item["score"] < self.min_score:
                    continue
                texts.append(normalized_item)

        return texts, ocr_time

    def _extract_paddle_lines(self, result):
        if result is None:
            return []

        if isinstance(result, dict):
            return [result]

        if isinstance(result, list) and result:
            first_item = result[0]
            if isinstance(first_item, list) and first_item and isinstance(first_item[0], list):
                return first_item
            return result

        return []

    def _iter_paddle_items(self, result):
        for item in self._extract_paddle_lines(result):
            if item is None:
                continue

            if isinstance(item, dict):
                boxes = item.get("dt_polys") or item.get("boxes") or item.get("polys") or []
                texts = item.get("rec_texts") or item.get("texts") or []
                scores = item.get("rec_scores") or item.get("scores") or []

                max_len = max(len(boxes), len(texts), len(scores), 0)
                for idx in range(max_len):
                    box = boxes[idx] if idx < len(boxes) else None
                    text = texts[idx] if idx < len(texts) else ""
                    score = scores[idx] if idx < len(scores) else 0.0
                    yield box, text, score
                continue

            if isinstance(item, (list, tuple)) and len(item) >= 2:
                box = item[0]
                text_info = item[1]
                if not text_info or len(text_info) < 2:
                    continue
                yield box, text_info[0], text_info[1]

    def _call_paddleocr(self, img):
        ocr_method = getattr(self.engine, "ocr", None)
        if callable(ocr_method):
            try:
                parameters = inspect.signature(ocr_method).parameters
            except (TypeError, ValueError):
                parameters = {}

            kwargs = {}
            if "cls" in parameters:
                kwargs["cls"] = False

            try:
                return ocr_method(img, **kwargs)
            except TypeError:
                if kwargs:
                    return ocr_method(img)
                raise

        predict_method = getattr(self.engine, "predict", None)
        if callable(predict_method):
            return predict_method(img)

        raise RuntimeError("PaddleOCR non espone un metodo OCR compatibile.")

    def _run_paddleocr(self, img, fallback_time):
        result = self._call_paddleocr(img)
        texts = []

        for box, text, score in self._iter_paddle_items(result):
            normalized_item = self._normalize_ocr_item(box, text, score)
            if normalized_item is None or normalized_item["score"] < self.min_score:
                continue

            texts.append(normalized_item)

        return texts, fallback_time

    def run_ocr(self, img):
        t0 = time.perf_counter()

        if self.engine_name == "rapidocr":
            texts, ocr_time = self._run_rapidocr(img)
        elif self.engine_name == "paddleocr":
            texts, ocr_time = self._run_paddleocr(img, time.perf_counter() - t0)
        else:
            raise ValueError(f"OCR engine non supportato: {self.engine_name}")

        if ocr_time <= 0:
            ocr_time = time.perf_counter() - t0

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
