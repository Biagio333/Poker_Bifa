import cv2
import numpy as np
from adbblitz import AdbShotUSB

ADB_PATH = "adb"          # oppure "/usr/bin/adb"
DEVICE_SERIAL = None      # metti il seriale se ne hai più di uno

def main():
    stream = AdbShotUSB(
        device_serial=DEVICE_SERIAL,
        adb_path=ADB_PATH,
        adb_host_address="127.0.0.1",
        adb_host_port=5037,
        sleep_after_exception=0.01,
        frame_buffer=1,              # meno buffer = meno lag
        lock_video_orientation=0,
        max_frame_rate=8,            # prova 6-10
        byte_package_size=131072,
        scrcpy_server_version="2.0", # se dà errore proviamo a cambiarla
        log_level="info",
        max_video_width=0,           # 0 = piena risoluzione
        start_server=True,
        connect_to_device=True,
    )

    try:
        while True:
            frame = stream.get_one_screenshot()

            if frame is None:
                continue

            # frame pieno
            frame_full = frame

            # copia ridotta per OCR/debug veloce
            frame_small = cv2.resize(frame_full, None, fx=0.4, fy=0.4)

            # qui fai OCR su frame_small
            # esempio:
            # result = ocr.readtext(frame_small)

            cv2.imshow("small", frame_small)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

    finally:
        try:
            stream.quit()
        except Exception:
            pass
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()