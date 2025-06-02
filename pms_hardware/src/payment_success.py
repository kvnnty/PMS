import os
import sqlite3

DB_FILE = './../../db/pms_db_file.db'

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

def mark_payment_success(plate_number):
    if not os.path.exists(DB_FILE):
        print("[ERROR] Database file does not exist.")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Check if there is any unpaid record for this plate
        cursor.execute('''
            SELECT COUNT(*) FROM vehicle_log
            WHERE car_plate = ? AND payment_status = '0'
        ''', (plate_number,))
        count = cursor.fetchone()[0]

        if count == 0:
            print(f"[INFO] No unpaid record found for {plate_number}")
            conn.close()
            return

        # Update payment_status to '1' for unpaid records
        cursor.execute('''
            UPDATE vehicle_log
            SET payment_status = '1'
            WHERE car_plate = ? AND payment_status = '0'
        ''', (plate_number,))

        conn.commit()
        conn.close()
        print(f"[UPDATED] Payment status set to 1 for {plate_number}")

    except sqlite3.Error as e:
        print(f"[ERROR] SQLite error: {e}")

# ==== TESTING USAGE ====
if __name__ == "__main__":
    plate = input("Enter plate number to mark as paid: ").strip().upper()
    mark_payment_success(plate)
