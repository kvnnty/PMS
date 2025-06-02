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
import threading
from uuid import uuid4

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
ALARM_DURATION = 10      # seconds for alerts
TAMPER_DISTANCE = 999.99 # cm, indicates sensor timeout or tampering

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

def initialize_database():
    """Create necessary tables if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicle_log (
            no INTEGER PRIMARY KEY AUTOINCREMENT,
            car_plate TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            exit_time TEXT,
            payment_status TEXT NOT NULL DEFAULT '0',
            due_payment REAL DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS unauthorized_exit_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_plate TEXT NOT NULL,
            alert_time TEXT NOT NULL,
            due_payment REAL,
            alert_type TEXT,
            resolved INTEGER DEFAULT 0,
            notes TEXT
        )
    ''')

    conn.commit()
    conn.close()

def detect_arduino_port():
    """Detect Arduino port based on platform."""
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
    """Read distance from Arduino serial."""
    if not arduino or arduino.in_waiting == 0:
        return None
    try:
        line = arduino.readline().decode('utf-8').strip()
        if line.startswith('DIST:'):
            return float(line.split(':')[1])
        return None
    except (UnicodeDecodeError, ValueError, IndexError):
        logger.warning("Failed to parse distance from Arduino.")
        return None

def get_unpaid_record(plate):
    """Retrieve unpaid record for a given plate."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT no, due_payment FROM vehicle_log
        WHERE car_plate = ? AND payment_status = '0'
        ORDER BY entry_time DESC LIMIT 1
    ''', (plate,))
    row = cursor.fetchone()
    conn.close()
    return row if row else None

def update_exit_log(record_id):
    """Update vehicle log with exit time and payment status."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE vehicle_log
        SET exit_time = ?, payment_status = '1'
        WHERE no = ?
    ''', (
        time.strftime('%Y-%m-%d %H:%M:%S'),
        record_id
    ))
    conn.commit()
    conn.close()

def log_unauthorized_exit(plate, due_payment, alert_type="UNPAID_EXIT"):
    """Log unauthorized exit or tampering alert."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO unauthorized_exit_alerts 
        (car_plate, alert_time, due_payment, alert_type, resolved, notes)
        VALUES (?, ?, ?, ?, 0, ?)
    ''', (
        plate,
        time.strftime('%Y-%m-%d %H:%M:%S'),
        due_payment,
        alert_type,
        f"Alert: {alert_type}. Plate: {plate}. Due: {due_payment}"
    ))
    conn.commit()
    conn.close()
    logger.warning(f"[{alert_type}] Plate {plate} triggered alert. Due: {due_payment}")

def trigger_alert(arduino, alert_type, duration=ALARM_DURATION):
    """Trigger alert on Arduino (PAYMENT_PENDING or TAMPERING)."""
    if not arduino:
        logger.warning(f"[{alert_type}] No Arduino connection. Simulating alert.")
        for _ in range(5):
            print("\a")
            time.sleep(0.2)
        return

    try:
        if alert_type == "PAYMENT_PENDING":
            arduino.write(b'2')
            logger.info(f"PAYMENT_PENDING alert activated for {duration} seconds")
        # elif alert_type == "TAMPERING":
        #     arduino.write(b'3')
        #     logger.info(f"TAMPERING alert activated for {duration} seconds")
        time.sleep(duration)
        arduino.write(b'S')
        logger.info(f"{alert_type} alert deactivated")
    except Exception as e:
        logger.error(f"Failed to trigger {alert_type} alert: {e}")

def alert_thread(arduino, alert_type, duration):
    """Run alert in a separate thread."""
    trigger_alert(arduino, alert_type, duration)

def signal_handler(sig, frame):
    """Handle program interruption."""
    logger.info("Interrupted by user. Shutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def main():
    initialize_database()

    arduino_port = detect_arduino_port()
    arduino = None
    if arduino_port:
        try:
            arduino = serial.Serial(arduino_port, 9600, timeout=1)
            time.sleep(2)
            arduino.flush()
            logger.info(f"Arduino connected on {arduino_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Arduino on {arduino_port}: {e}")
    else:
        logger.warning("Arduino not detected. Continuing without hardware control.")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Camera could not be opened.")
        sys.exit(1)

    cv2.namedWindow('Parking System Exit point Camera Feed', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Parking System Exit point Camera Feed', 800, 600)

    plate_buffer = []
    last_processed_plate = None
    last_exit_time = 0
    last_alert_time = 0
    last_tamper_time = 0
    ALERT_COOLDOWN = 30  # seconds to prevent repeated alerts

    logger.info("Exit system with alert subsystem ready. Press Ctrl+C to exit.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("Failed to read frame from camera.")
                continue

            distance = read_distance(arduino) or (MAX_DISTANCE - 1)
            annotated = frame.copy()

            # Check for tampering (sensor timeout or invalid distance)
            now = time.time()
            # if distance >= TAMPER_DISTANCE and (now - last_tamper_time) > ALERT_COOLDOWN:
            #     log_unauthorized_exit("UNKNOWN", 0, "TAMPERING")
            #     alert_thread_instance = threading.Thread(
            #         target=alert_thread,
            #         args=(arduino, "TAMPERING", ALARM_DURATION)
            #     )
            #     alert_thread_instance.daemon = True
            #     alert_thread_instance.start()
            #     last_tamper_time = now
            #     logger.info("[TAMPERING] Suspicious sensor reading detected.")

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
                            record_data = get_unpaid_record(common)

                            if record_data:
                                record_id, due_payment = record_data

                                if due_payment > 0 and (now - last_alert_time) > ALERT_COOLDOWN:
                                    logger.warning(f"[UNAUTHORIZED EXIT ATTEMPT] Plate {common} owes {due_payment}")
                                    log_unauthorized_exit(common, due_payment, "PAYMENT_PENDING")
                                    alert_thread_instance = threading.Thread(
                                        target=alert_thread,
                                        args=(arduino, "PAYMENT_PENDING", ALARM_DURATION)
                                    )
                                    alert_thread_instance.daemon = True
                                    alert_thread_instance.start()
                                    last_alert_time = now
                                    logger.info(f"[GATE BLOCKED] Gate remains closed for plate {common}")
                                else:
                                    update_exit_log(record_id)
                                    logger.info(f"[EXIT] Plate {common} marked as exited.")
                                    if arduino:
                                        try:
                                            arduino.write(b'1')
                                            time.sleep(GATE_OPEN_TIME)
                                            arduino.write(b'0')
                                        except Exception as e:
                                            logger.error(f"Failed to control gate: {e}")

                                last_processed_plate = common
                                last_exit_time = now
                            else:
                                logger.info(f"[SKIPPED] No entry record found for plate {common}.")

                        plate_buffer.clear()

                    time.sleep(0.5)

            cv2.putText(annotated, "ALERT SYSTEM ACTIVE", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            cv2.imshow('Parking System Exit point Camera Feed', annotated)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except Exception as e:
        logger.exception("An error occurred during execution.")
    finally:
        cap.release()
        if arduino:
            try:
                arduino.write(b'S')  # Stop any ongoing alerts
                arduino.close()
            except Exception as e:
                logger.error(f"Failed to close Arduino connection: {e}")
        cv2.destroyAllWindows()
        logger.info("Camera and serial connections closed. Program terminated.")

if __name__ == '__main__':
    main()