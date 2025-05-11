import csv
import os
from datetime import datetime
import serial
import serial.tools.list_ports
import time

LOG_FILE = "plates_log.csv"
PRICE_PER_HOUR = 200  # RWF per hour
ser = None

def listen_to_arduino(arduino_port, baud=9600):
    global ser
    try:
        ser = serial.Serial(arduino_port, baud, timeout=2)
        time.sleep(2)
        print(f"🔌 Listening on {arduino_port}...")

        while True:
            line = ser.readline().decode('utf-8').strip()
            if line:
                print("📨 Received:", line)
                process_message(line)

    except serial.SerialException as e:
        print("❌ Serial error:", e)
    except KeyboardInterrupt:
        print("\n🔚 Exiting...")
    finally:
        if ser and ser.is_open:
            ser.close()

def process_message(message):
    if "PLATE:" in message and "BALANCE:" in message:
        try:
            parts = message.split("|")
            plate = parts[0].split("PLATE:")[1]
            balance = int(parts[1].split("BALANCE:")[1])
            print(f"✅ Plate: {plate} | Balance: {balance} RWF")

            entry_row = lookup_unpaid_entry(plate)
            if entry_row:
                compute_and_log_payment(entry_row, balance)
            else:
                print("❌ Plate not found or already paid.")
        except Exception as e:
            print(f"⚠️ Failed to process message: {e}")
    else:
        print("⚠️ Unrecognized format.")

def lookup_unpaid_entry(plate):
    if not os.path.exists(LOG_FILE):
        return None

    with open(LOG_FILE, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row['Plate Number'] == plate and row['Payment Status'] == '0':
                return row
    return None

def compute_and_log_payment(entry_row, balance):
    plate = entry_row['Plate Number']
    entry_time = datetime.fromisoformat(entry_row['Timestamp'])
    now = datetime.now()
    duration = now - entry_time
    duration_hours = round(duration.total_seconds() / 3600, 2)
    amount_due = round(duration_hours * PRICE_PER_HOUR)

    print(f"🕒 Duration: {duration_hours} hrs | 💸 Due: {amount_due} RWF")

    if balance < amount_due:
        print("❌ Insufficient balance!")
        return

    command = f"PAY:{amount_due}\n"
    print(f"➡️ Sending command to Arduino: {command.strip()}")
    global ser
    ser.write(command.encode())

    response = ser.readline().decode().strip()
    if response == "DONE":
        print("✅ Payment confirmed by Arduino.")
        update_plate_log(
            plate=plate,
            exit_time=now.isoformat(),
            duration_hr=str(duration_hours),
            amount=str(amount_due)
        )
    else:
        print(f"❌ Payment failed or missing DONE signal: {response}")

def update_plate_log(plate, exit_time, duration_hr, amount):
    updated_rows = []
    with open(LOG_FILE, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row['Plate Number'] == plate and row['Payment Status'] == '0':
                row['Exit Time'] = exit_time
                row['Duration (hr)'] = duration_hr
                row['Amount'] = amount
                row['Payment Status'] = '1'
            updated_rows.append(row)

    fieldnames = ['Plate Number', 'Timestamp', 'Payment Status', 'Exit Time', 'Duration (hr)', 'Amount']
    with open(LOG_FILE, "w", newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    print("📝 plates_log.csv updated with full payment info.")

def find_serial_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if "Arduino" in p.description or "CH340" in p.description or "ttyUSB" in p.device:
            return p.device
    return ports[0].device if ports else None

if __name__ == "__main__":
    port = find_serial_port()
    if port:
        listen_to_arduino(port)
    else:
        print("❌ No serial port found.")
