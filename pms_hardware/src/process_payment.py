import serial
import time
import serial.tools.list_ports
import platform
import sqlite3
from datetime import datetime

DB_FILE = './../../db/pms_db_file.db'
RATE_PER_MINUTE = 5  # Amount charged per minute

def detect_arduino_port():
    ports = list(serial.tools.list_ports.comports())
    system = platform.system()
    for port in ports:
        if system == "Linux":
            if "ttyUSB" in port.device or "ttyACM" in port.device:
                return port.device
        elif system == "Darwin":
            if "usbmodem" in port.device or "usbserial" in port.device:
                return port.device
        elif system == "Windows":
            if "COM5" in port.device:
                return port.device
    return None

def parse_arduino_data(line):
    try:
        parts = line.strip().split(',')
        if len(parts) != 2:
            return None, None
        plate = parts[0].strip()
        balance_str = ''.join(c for c in parts[1] if c.isdigit())
        if balance_str:
            return plate, int(balance_str)
    except Exception as e:
        print(f"[ERROR] Failed to parse Arduino data: {e}")
    return None, None

def process_payment(plate, balance, ser):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT no, entry_time FROM vehicle_log 
            WHERE car_plate = ? AND payment_status = '0' 
            ORDER BY no DESC LIMIT 1
        ''', (plate,))
        row = cursor.fetchone()

        if not row:
            print("[PAYMENT] No unpaid record found for plate.")
            return

        record_id, entry_time_str = row
        entry_time = datetime.strptime(entry_time_str, '%Y-%m-%d %H:%M:%S')
        exit_time = datetime.now()
        minutes_spent = int((exit_time - entry_time).total_seconds() / 60) + 1
        due_amount = minutes_spent * RATE_PER_MINUTE

        if balance < due_amount:
            print("[PAYMENT] Insufficient balance.")
            ser.write(b'I\n')
            return

        new_balance = balance - due_amount

        # Wait for Arduino "READY"
        print("[WAIT] Waiting for Arduino READY...")
        start_time = time.time()
        while True:
            if ser.in_waiting:
                response = ser.readline().decode().strip()
                print(f"[ARDUINO] {response}")
                if response == "READY":
                    break
            if time.time() - start_time > 5:
                print("[ERROR] Timeout waiting for Arduino READY")
                return

        # Send balance and wait for confirmation
        ser.write(f"{new_balance}\r\n".encode())
        print(f"[ARDUINO] Sent new balance: {new_balance}")

        start_time = time.time()
        while True:
            if ser.in_waiting:
                response = ser.readline().decode().strip()
                print(f"[ARDUINO] {response}")
                if "DONE" in response:
                    print("[ARDUINO] Write confirmed")

                    # Update DB
                    cursor.execute('''
                        UPDATE vehicle_log 
                        SET exit_time = ?, due_payment = ?, payment_status = '1' 
                        WHERE no = ?
                    ''', (
                        exit_time.strftime('%Y-%m-%d %H:%M:%S'),
                        str(due_amount),
                        record_id
                    ))
                    conn.commit()
                    print("[PAYMENT] Payment successful and record updated.")
                    break
            if time.time() - start_time > 10:
                print("[ERROR] Timeout waiting for DONE")
                break

    except Exception as e:
        print(f"[ERROR] Payment process failed: {e}")
    finally:
        conn.close()

def main():
    port = detect_arduino_port()
    if not port:
        print("[ERROR] Arduino not found.")
        return

    try:
        ser = serial.Serial(port, 9600, timeout=1)
        print(f"[CONNECTED] Listening on {port}")
        time.sleep(2)
        ser.reset_input_buffer()

        while True:
            if ser.in_waiting:
                line = ser.readline().decode().strip()
                print(f"[ARDUINO] Received: {line}")
                plate, balance = parse_arduino_data(line)
                if plate and balance is not None:
                    process_payment(plate, balance, ser)

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        if ser:
            ser.close()
            print("[CLOSED] Serial connection closed.")

if __name__ == "__main__":
    main()
