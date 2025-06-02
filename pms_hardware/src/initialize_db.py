import sqlite3
import os
import logging
from logging.handlers import RotatingFileHandler

# === CONFIG ===
DB_PATH = './../../db/pms_db_file.db'
LOG_FILE = './../logs/parking_system_db.log'

# === LOGGING SETUP ===
log_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
logging.basicConfig(
    handlers=[log_handler],
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

def ensure_db_directory():
    """Ensure the database directory exists."""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        logger.info(f"Created database directory: {db_dir}")

def initialize_database():
    """Create necessary tables if they don't exist."""
    try:
        ensure_db_directory()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Create vehicle_log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vehicle_log (
                no INTEGER PRIMARY KEY AUTOINCREMENT,
                car_plate TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                exit_time TEXT,
                payment_status TEXT NOT NULL DEFAULT '0',
                due_payment REAL DEFAULT 0,
                is_exited INTEGER DEFAULT 0
            )
        ''')
        logger.info("Initialized vehicle_log table")

        # Create unauthorized_exit_alerts table
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
        logger.info("Initialized unauthorized_exit_alerts table")

        conn.commit()
        logger.info("Database initialization completed successfully")
    except sqlite3.Error as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    finally:
        conn.close()
        logger.info("Database connection closed")

if __name__ == '__main__':
    logger.info("Starting database initialization")
    try:
        initialize_database()
        print("Database tables initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")
        logger.error(f"Error initializing database: {e}")