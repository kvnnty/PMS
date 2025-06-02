# app.py
from flask import Flask, jsonify
import sqlite3

from flask_cors import CORS
app = Flask(__name__)

DB_PATH = './../db/pms_db_file.db'  # Update this to match your file location

CORS(app)

def fetch_all_records():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicle_log")  # Replace with your actual table name
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.route('/')
def home():
    return 'Hello from Flask!'

@app.route('/api/vehicles')
def vehicles():
    data = fetch_all_records()
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True, port=8000)
