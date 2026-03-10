import cv2
import threading


class LatestFrameGrabber:
    def __init__(self, device="/dev/video42"):
        self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.cap.isOpened():
            raise RuntimeError(f"Impossibile aprire {device}")
        self.lock = threading.Lock()
        self.frame = None
        self.running = True
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()

    def _reader(self):
        while self.running:
            ok, frame = self.cap.read()
            if ok:
                with self.lock:
                    self.frame = frame

    def get_latest(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def close(self):
        self.running = False
        self.thread.join(timeout=1)
        self.cap.release()


grabber = LatestFrameGrabber("/dev/video42")

try:
    while True:
        frame = grabber.get_latest()
        if frame is None:
            continue

        # qui OCR / crop / template matching
        cv2.imshow("latest", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
finally:
    grabber.close()
    cv2.destroyAllWindows()