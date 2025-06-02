import serial
import time
import serial.tools.list_ports
import platform
from datetime import datetime
import os
import sqlite3

DB_FILE = './../../db/pms_db_file.db'
RATE_PER_MINUTE = 5  # Amount charged per minute

# Initialize SQLite DB and create table if not exists
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicle_log (
            no INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_time TEXT,
            exit_time TEXT,
            car_plate TEXT,
            due_payment TEXT,
            payment_status TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

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
            if "COM" in port.device:
                return port.device
    return None


def parse_arduino_data(line):
    try:
        parts = line.strip().split(',')
        print(f"[ARDUINO] Parsed parts: {parts}")
        if len(parts) != 2:
            return None, None
        plate = parts[0].strip()

        # Clean the balance string by removing non-digit characters
        balance_str = ''.join(c for c in parts[1] if c.isdigit())
        print(f"[ARDUINO] Cleaned balance: {balance_str}")

        if balance_str:
            balance = int(balance_str)
            return plate, balance
        else:
            return None, None
    except ValueError as e:
        print(f"[ERROR] Value error in parsing: {e}")
        return None, None


def process_payment(plate, balance, ser):
    if not os.path.exists(DB_FILE):
        print("[ERROR] Database file does not exist.")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Find unpaid record for this plate (payment_status = '0')
        cursor.execute('''
            SELECT rowid, entry_time, payment_status FROM vehicle_log
            WHERE car_plate = ? AND payment_status = '0'
            ORDER BY entry_time ASC
        ''', (plate,))
        records = cursor.fetchall()

        if not records:
            print("[PAYMENT] Plate not found or already paid.")
            conn.close()
            return

        # Process the first unpaid record found
        rowid, entry_time_str, payment_status = records[0]
        entry_time = datetime.strptime(entry_time_str, '%Y-%m-%d %H:%M:%S')
        exit_time = datetime.now()
        minutes_spent = int((exit_time - entry_time).total_seconds() / 60) + 1
        amount_due = minutes_spent * RATE_PER_MINUTE

        if balance < amount_due:
            print("[PAYMENT] Insufficient balance")
            ser.write(b'I\n')
            conn.close()
            return

        new_balance = balance - amount_due

        # Wait for Arduino to send "READY"
        print("[WAIT] Waiting for Arduino to be READY...")
        start_time = time.time()
        while True:
            if ser.in_waiting:
                arduino_response = ser.readline().decode().strip()
                print(f"[ARDUINO] {arduino_response}")
                if arduino_response == "READY":
                    break
            if time.time() - start_time > 5:
                print("[ERROR] Timeout waiting for Arduino READY")
                conn.close()
                return

        # Send new balance
        ser.write(f"{new_balance}\r\n".encode())
        print(f"[PAYMENT] Sent new balance {new_balance}")

        # Wait for confirmation with timeout
        start_time = time.time()
        print("[WAIT] Waiting for Arduino confirmation...")
        while True:
            if ser.in_waiting:
                confirm = ser.readline().decode().strip()
                print(f"[ARDUINO] {confirm}")
                if "DONE" in confirm:
                    print("[ARDUINO] Write confirmed")

                    # Update exit_time, amount_due, payment_status in DB
                    cursor.execute('''
                        UPDATE vehicle_log
                        SET exit_time = ?, amount_due = ?, payment_status = '1'
                        WHERE rowid = ?
                    ''', (exit_time.strftime('%Y-%m-%d %H:%M:%S'), str(amount_due), rowid))

                    conn.commit()
                    break

            if time.time() - start_time > 10:
                print("[ERROR] Timeout waiting for confirmation")
                break

            time.sleep(0.1)

        conn.close()

    except Exception as e:
        print(f"[ERROR] Payment processing failed: {e}")


def main():
    port = detect_arduino_port()
    if not port:
        print("[ERROR] Arduino not found")
        return

    try:
        ser = serial.Serial(port, 9600, timeout=1)
        print(f"[CONNECTED] Listening on {port}")
        time.sleep(2)

        ser.reset_input_buffer()

        while True:
            if ser.in_waiting:
                line = ser.readline().decode().strip()
                print(f"[SERIAL] Received: {line}")
                plate, balance = parse_arduino_data(line)
                if plate and balance is not None:
                    process_payment(plate, balance, ser)

    except KeyboardInterrupt:
        print("[EXIT] Program terminated")
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        if 'ser' in locals():
            ser.close()


if __name__ == "__main__":
    main()
