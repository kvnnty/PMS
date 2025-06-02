import platform
import cv2
from ultralytics import YOLO
import pytesseract
import os
import time
import serial
import serial.tools.list_ports
import sqlite3
from collections import Counter, deque
import logging
from logging.handlers import RotatingFileHandler
import signal
import sys

# === CONFIG ===
SAVE_DIR = './../plates'
DB_FILE = './../../db/pms_db_file.db'
MODEL_PATH = './../models/weights/best.pt'
LOG_FILE = './../logs/parking_system_entry.log'

ENTRY_COOLDOWN = 300      # seconds
MAX_DISTANCE = 50         # cm
MIN_DISTANCE = 0          # cm
CAPTURE_THRESHOLD = 3     # frames
GATE_OPEN_TIME = 15       # seconds

# Compact display settings
MAX_DISPLAY_LOGS = 4
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.3
FONT_THICKNESS = 0.8
SMALL_FONT_SCALE = 0.3

# === LOGGING SETUP ===
log_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
logging.basicConfig(
    handlers=[log_handler],
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

# Global variables for display
system_status = {
    'arduino_connected': False,
    'camera_status': 'OK',
    'last_error': None,
    'current_distance': None,
    'detected_plates': [],
    'last_action': None,
    'gate_status': 'CLOSED'
}

class DisplayLogger:
    def __init__(self):
        self.logs = deque(maxlen=MAX_DISPLAY_LOGS)
    
    def add_log(self, level, message):
        if level not in ['ERROR', 'SUCCESS', 'INFO']:  # Only allow specified message types
            return
        if level == 'INFO' and not message.startswith('Detected plate'):  # Only allow detected plate for INFO
            return
        timestamp = time.strftime('%H:%M:%S')
        log_entry = {
            'time': timestamp,
            'level': level,
            'message': message,
            'color': self.get_color_for_level(level)
        }
        self.logs.append(log_entry)
        
        # Log to file
        if level == 'ERROR':
            logger.error(message)
        elif level == 'SUCCESS':
            logger.info(f"SUCCESS: {message}")
        else:
            logger.info(message)
    
    def get_color_for_level(self, level):
        colors = {
            'ERROR': (0, 0, 255),      # Red
            'SUCCESS': (0, 255, 0),    # Green
            'INFO': (255, 255, 255)    # White
        }
        return colors.get(level, (255, 255, 255))

display_logger = DisplayLogger()

def draw_text_with_background(img, text, position, font_scale=0.4, color=(255, 255, 255), bg_color=(0, 0, 0), thickness=1):
    (text_width, text_height), baseline = cv2.getTextSize(text, FONT, font_scale, thickness)
    x, y = position
    cv2.rectangle(img, (x - 3, y - text_height - 3), (x + text_width + 3, y + baseline + 3), bg_color, -1)
    cv2.putText(img, text, (x, y), FONT, font_scale, color, thickness)
    return text_height + 8


def draw_compact_plates(frame):
    if system_status['detected_plates']:
        height, width = frame.shape[:2]
        panel_width = 180
        panel_height = 60
        start_x = width - panel_width - 10
        
        cv2.rectangle(frame, (start_x, 10), (width - 10, 10 + panel_height), (0, 0, 0), -1)
        cv2.rectangle(frame, (start_x, 10), (width - 10, 10 + panel_height), (100, 100, 100), 1)
        
        y_offset = 25
        draw_text_with_background(frame, "PLATES", (start_x + 5, y_offset), 0.5, (0, 255, 255))
        y_offset += 20
        
        for plate in system_status['detected_plates'][-2:]:
            draw_text_with_background(frame, plate, (start_x + 5, y_offset), SMALL_FONT_SCALE, (255, 255, 0))
            y_offset += 18

def draw_compact_logs(frame):
    if not display_logger.logs:
        return
    
    height, width = frame.shape[:2]
    log_panel_width = 400
    log_panel_height = min(100, 25 + len(display_logger.logs) * 18)
    start_y = height - log_panel_height - 10
    
    cv2.rectangle(frame, (10, start_y), (log_panel_width, height - 10), (0, 0, 0), -1)
    cv2.rectangle(frame, (10, start_y), (log_panel_width, height - 10), (100, 100, 100), 1)
    
    y_offset = start_y + 20
    draw_text_with_background(frame, "LOGS", (15, y_offset), 0.5, (0, 255, 255))
    y_offset += 20
    
    for log_entry in list(display_logger.logs)[-4:]:
        log_text = f"[{log_entry['time']}] {log_entry['level']}: {log_entry['message']}"
        if len(log_text) > 50:
            log_text = log_text[:47] + "..."
        
        draw_text_with_background(frame, log_text, (15, y_offset), SMALL_FONT_SCALE, log_entry['color'])
        y_offset += 16

def draw_small_error_overlay(frame, error_message):
    height, width = frame.shape[:2]
    error_text = f"ERROR: {error_message}"
    if len(error_text) > 40:
        error_text = error_text[:37] + "..."
    
    text_size = cv2.getTextSize(error_text, FONT, 0.5, 2)[0]
    banner_width = text_size[0] + 20
    banner_height = 30
    start_x = (width - banner_width) // 2
    start_y = 10
    
    cv2.rectangle(frame, (start_x, start_y), (start_x + banner_width, start_y + banner_height), (0, 0, 255), -1)
    cv2.rectangle(frame, (start_x, start_y), (start_x + banner_width, start_y + banner_height), (255, 255, 255), 2)
    cv2.putText(frame, error_text, (start_x + 10, start_y + 20), FONT, 0.5, (255, 255, 255), 2)

def draw_minimal_action_indicator(frame):
    if system_status['last_action']:
        height, width = frame.shape[:2]
        action_text = system_status['last_action']
        if len(action_text) > 20:
            action_text = action_text[:17] + "..."
        
        text_size = cv2.getTextSize(action_text, FONT, SMALL_FONT_SCALE, 1)[0]
        start_x = width - text_size[0] - 20
        start_y = height - 20
        
        cv2.rectangle(frame, (start_x - 5, start_y - 15), (start_x + text_size[0] + 5, start_y + 5), (0, 0, 0), -1)
        cv2.putText(frame, action_text, (start_x, start_y), FONT, SMALL_FONT_SCALE, (255, 255, 0), 1)

# === YOLO MODEL LOAD ===
try:
    model = YOLO(MODEL_PATH)
    model.verbose = False
except Exception as e:
    display_logger.add_log('ERROR', f'Failed to load YOLO model: {str(e)}')
    model = None

# === INIT ===
os.makedirs(SAVE_DIR, exist_ok=True)

def detect_arduino_port():
    try:
        for port in serial.tools.list_ports.comports():
            dev = port.device
            if platform.system() == 'Linux' and 'ttyACM' in dev:
                return dev
            if platform.system() == 'Darwin' and ('usbmodem' in dev or 'usbserial' in dev):
                return dev
            if platform.system() == 'Windows' and 'COM6' in dev:
                return dev
        return None
    except Exception as e:
        display_logger.add_log('ERROR', f'Arduino detection failed: {str(e)}')
        return None

def read_distance(arduino):
    if not arduino or arduino.in_waiting == 0:
        return None
    try:
        val = arduino.readline().decode('utf-8').strip()
        distance = float(val)
        system_status['current_distance'] = distance
        return distance
    except (UnicodeDecodeError, ValueError):
        return None

def has_unpaid_record(plate):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM vehicle_log 
            WHERE car_plate = ? AND payment_status = '0'
        ''', (plate,))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception as e:
        display_logger.add_log('ERROR', f'Database query failed: {str(e)}')
        return False

def insert_vehicle_log(plate):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO vehicle_log (entry_time, exit_time, car_plate, due_payment, payment_status, is_exited)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            time.strftime('%Y-%m-%d %H:%M:%S'),
            '', plate, '', '0', '0'
        ))
        conn.commit()
        conn.close()
        display_logger.add_log('SUCCESS', f'Vehicle {plate} logged successfully')
        system_status['last_action'] = f'Logged {plate}'
    except Exception as e:
        display_logger.add_log('ERROR', f'Failed to log vehicle {plate}: {str(e)}')

def signal_handler(sig, frame):
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def main():
    # === Arduino Init ===
    arduino_port = detect_arduino_port()
    arduino = None
    if arduino_port:
        try:
            arduino = serial.Serial(arduino_port, 9600, timeout=1)
            time.sleep(2)
        except Exception as e:
            display_logger.add_log('ERROR', f'Arduino connection failed: {str(e)}')
            system_status['arduino_connected'] = False
    else:
        display_logger.add_log('ERROR', 'Arduino not detected')
        system_status['arduino_connected'] = False

    # === Camera Init ===
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        display_logger.add_log('ERROR', 'Camera could not be opened')
        system_status['camera_status'] = 'FAILED'
        sys.exit(1)

    cv2.namedWindow('Parking System Entry Point', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Parking System Entry Point', 900, 600)

    plate_buffer = []
    last_saved_plate = None
    last_entry_time = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                system_status['camera_status'] = 'ERROR'
                continue
            else:
                system_status['camera_status'] = 'OK'

            distance = read_distance(arduino) or (MAX_DISTANCE - 1)
            annotated = frame.copy()

            if MIN_DISTANCE <= distance <= MAX_DISTANCE:
                if model is None:
                    system_status['last_error'] = "YOLO model not loaded"
                else:
                    try:
                        results = model(frame)[0]
                        annotated = results.plot()

                        current_detections = []
                        for box in results.boxes:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            plate_img = frame[y1:y2, x1:x2]

                            try:
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
                                        current_detections.append(plate)
                                        display_logger.add_log('INFO', f'Detected plate: {plate}')

                            except Exception:
                                pass  # Skip OCR errors silently

                        system_status['detected_plates'] = current_detections

                        if len(plate_buffer) >= CAPTURE_THRESHOLD:
                            common = Counter(plate_buffer).most_common(1)[0][0]
                            now = time.time()

                            if not has_unpaid_record(common):
                                if common != last_saved_plate or (now - last_entry_time) > ENTRY_COOLDOWN:
                                    insert_vehicle_log(common)
                                    if arduino:
                                        try:
                                            arduino.write(b'1')
                                            system_status['gate_status'] = 'OPEN'
                                            display_logger.add_log('SUCCESS', f'Gate opened for {common}')
                                            time.sleep(GATE_OPEN_TIME)
                                            arduino.write(b'0')
                                            system_status['gate_status'] = 'CLOSED'
                                            display_logger.add_log('INFO', 'Gate closed')
                                        except Exception as e:
                                            display_logger.add_log('ERROR', f'Gate control error: {str(e)}')

                                    last_saved_plate = common
                                    last_entry_time = now
                            plate_buffer.clear()

                    except Exception as e:
                        display_logger.add_log('ERROR', f'Detection processing error: {str(e)}')
                        system_status['last_error'] = str(e)

            draw_compact_plates(annotated)
            draw_compact_logs(annotated)
            draw_minimal_action_indicator(annotated)
            
            if system_status.get('last_error'):
                draw_small_error_overlay(annotated, system_status['last_error'])

            cv2.imshow('Parking System Entry Point', annotated)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except Exception as e:
        display_logger.add_log('ERROR', f'Critical system error: {str(e)}')
        logger.exception("Critical error occurred during execution")
    finally:
        cap.release()
        if arduino:
            arduino.close()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()