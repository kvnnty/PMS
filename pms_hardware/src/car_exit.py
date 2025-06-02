import platform
import cv2
from ultralytics import YOLO
import pytesseract
import os
import time
import serial
import serial.tools.list_ports
import sqlite3
from collections import Counter
import logging
from logging.handlers import RotatingFileHandler
import signal
import sys

# === CONFIG ===
SAVE_DIR = './../plates'
DB_FILE = './../../db/pms_db_file.db'
MODEL_PATH = './../models/weights/best.pt'
LOG_FILE = './../logs/parking_system_exit.log'

EXIT_COOLDOWN = 300      # seconds
MAX_DISTANCE = 50        # cm
MIN_DISTANCE = 0         # cm
CAPTURE_THRESHOLD = 3    # frames
GATE_OPEN_TIME = 15      # seconds

# === LOGGING SETUP ===
log_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
logging.basicConfig(
    handlers=[log_handler],
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

# === YOLO MODEL LOAD ===
model = YOLO(MODEL_PATH)
model.verbose = False

# === INIT ===
os.makedirs(SAVE_DIR, exist_ok=True)

def detect_arduino_port():
    for port in serial.tools.list_ports.comports():
        dev = port.device
        if platform.system() == 'Linux' and 'ttyACM' in dev:
            return dev
        if platform.system() == 'Darwin' and ('usbmodem' in dev or 'usbserial' in dev):
            return dev
        if platform.system() == 'Windows' and 'COM6' in dev:
            return dev
    return None

def read_distance(arduino):
    if not arduino or arduino.in_waiting == 0:
        return None
    try:
        val = arduino.readline().decode('utf-8').strip()
        return float(val)
    except (UnicodeDecodeError, ValueError):
        return None

def get_unpaid_record(plate):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT no FROM vehicle_log
        WHERE car_plate = ? AND payment_status = '0'
        ORDER BY entry_time DESC LIMIT 1
    ''', (plate,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def update_exit_log(record_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE vehicle_log
        SET exit_time = ?, payment_status = '1', is_exited = '1'
        WHERE no = ?
    ''', (
        time.strftime('%Y-%m-%d %H:%M:%S'),
        record_id
    ))
    conn.commit()
    conn.close()

def signal_handler(sig, frame):
    logger.info("Interrupted by user. Shutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def main():
    # === Arduino Init ===
    arduino_port = detect_arduino_port()
    arduino = None
    if arduino_port:
        arduino = serial.Serial(arduino_port, 9600, timeout=1)
        time.sleep(2)
        logger.info(f"Arduino connected on {arduino_port}")
    else:
        logger.warning("Arduino not detected. Continuing without hardware control.")

    # === Camera Init ===
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Camera could not be opened.")
        sys.exit(1)

    cv2.namedWindow('Parking System Exit point Camera Feed', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Parking System Exit point Camera Feed', 800, 600)

    # === State ===
    plate_buffer = []
    last_processed_plate = None
    last_exit_time = 0

    logger.info("Exit system ready. Press Ctrl+C to exit.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("Failed to read frame from camera.")
                continue

            distance = read_distance(arduino) or (MAX_DISTANCE - 1)
            annotated = frame.copy()

            if MIN_DISTANCE <= distance <= MAX_DISTANCE:
                results = model(frame)[0]
                annotated = results.plot()

                for box in results.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    plate_img = frame[y1:y2, x1:x2]

                    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
                    blur = cv2.GaussianBlur(gray, (5, 5), 0)
                    thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

                    text = pytesseract.image_to_string(
                        thresh,
                        config='--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                    ).strip().replace(' ', '')

                    if text.startswith('RA') and len(text) >= 7:
                        plate = text[:7]
                        pr, dg, su = plate[:3], plate[3:6], plate[6]
                        if pr.isalpha() and dg.isdigit() and su.isalpha():
                            plate_buffer.append(plate)

                    if len(plate_buffer) >= CAPTURE_THRESHOLD:
                        common = Counter(plate_buffer).most_common(1)[0][0]
                        now = time.time()

                        if common != last_processed_plate or (now - last_exit_time) > EXIT_COOLDOWN:
                            record_id = get_unpaid_record(common)
                            if record_id:
                                update_exit_log(record_id)
                                logger.info(f"[EXIT] Plate {common} marked as exited.")

                                if arduino:
                                    arduino.write(b'1')
                                    time.sleep(GATE_OPEN_TIME)
                                    arduino.write(b'0')

                                last_processed_plate = common
                                last_exit_time = now
                            else:
                                logger.info(f"[SKIPPED] No unpaid entry found for plate {common}.")

                        plate_buffer.clear()

                    time.sleep(0.5)

            cv2.imshow('Parking System Exit point Camera Feed', annotated)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except Exception as e:
        logger.exception("An error occurred during execution.")
    finally:
        cap.release()
        if arduino:
            arduino.close()
        cv2.destroyAllWindows()
        logger.info("Camera and serial connections closed. Program terminated.")

if __name__ == '__main__':
    main()
