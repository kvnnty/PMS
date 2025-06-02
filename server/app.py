from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
from contextlib import contextmanager
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

# === CONFIG ===
DB_PATH = './../db/pms_db_file.db'
LOG_FILE = './logs/flask_app.log'

# === LOGGING SETUP ===
log_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
logging.basicConfig(
    handlers=[log_handler],
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

# Restrict CORS to Next.js development server
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

@contextmanager
def get_db_connection():
    """Manage database connections with context manager."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

@app.route('/')
def home():
    return jsonify({"message": "Welcome to the Parking System API"})

@app.route('/api/vehicles', methods=['GET'])
def vehicles():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vehicle_log")
            rows = cursor.fetchall()
            return jsonify([dict(row) for row in rows]), 200
    except Exception as e:
        logger.error(f"Error fetching vehicles: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/vehicles/<plate>', methods=['GET'])
def vehicle_by_plate(plate):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vehicle_log WHERE car_plate = ?", (plate,))
            row = cursor.fetchone()
            if row:
                return jsonify(dict(row)), 200
            return jsonify({"error": "Vehicle not found"}), 404
    except Exception as e:
        logger.error(f"Error fetching vehicle {plate}: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/alerts', methods=['GET'])
def alerts():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM unauthorized_exit_alerts")
            rows = cursor.fetchall()
            return jsonify([dict(row) for row in rows]), 200
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/resolve_alert/<int:id>', methods=['POST'])
def resolve_alert(id):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE unauthorized_exit_alerts SET resolved = 1 WHERE id = ?", (id,))
            if cursor.rowcount == 0:
                return jsonify({"error": "Alert not found"}), 404
            conn.commit()
            logger.info(f"Alert {id} marked as resolved")
            return jsonify({"message": "Alert resolved successfully"}), 200
    except Exception as e:
        logger.error(f"Error resolving alert {id}: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/stats', methods=['GET'])
def stats():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total_vehicles FROM vehicle_log")
            total_vehicles = cursor.fetchone()['total_vehicles']
            cursor.execute("SELECT COUNT(*) as unpaid_vehicles FROM vehicle_log WHERE payment_status = '0'")
            unpaid_vehicles = cursor.fetchone()['unpaid_vehicles']
            cursor.execute("SELECT COUNT(*) as active_alerts FROM unauthorized_exit_alerts WHERE resolved = 0")
            active_alerts = cursor.fetchone()['active_alerts']
            return jsonify({
                "total_vehicles": total_vehicles,
                "unpaid_vehicles": unpaid_vehicles,
                "active_alerts": active_alerts
            }), 200
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)