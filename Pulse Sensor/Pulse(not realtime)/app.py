from flask import Flask, jsonify, render_template, send_from_directory, request, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import serial
import threading
import time
import os
from dotenv import load_dotenv
import re
from sqlalchemy import text

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Database Configuration
db_user = os.getenv("DB_USER", "admin")
db_password = os.getenv("DB_PASSWORD", "tcl")
db_endpoint = os.getenv("DB_ENDPOINT", "localhost")
db_name = os.getenv("DB_NAME", "local_database")

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{db_user}:{db_password}@{db_endpoint}/{db_name}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    records = db.relationship('BpmRecord', backref='user', lazy=True)

class BpmRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bpm = db.Column(db.Integer, nullable=False)
    spo2 = db.Column(db.Float, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Ensure tables are created
with app.app_context():
    try:
        db.create_all()
        try:
            db.session.execute(text('ALTER TABLE bpm_record ADD COLUMN spo2 FLOAT'))
        except Exception:
            pass
    except Exception as e:
        print("Database error:", e)

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory('assets', filename)

bpm_value = 0
spo2_value = 0.0
sensor_status = "waiting"
stabilization_progress = 0
last_save_time = 0
reading_start_time = None
session_completed = False

# mở serial
try:
    ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=0.1)
    time.sleep(2)
    ser.reset_input_buffer()
    print("Serial connected")
except Exception as e:
    print("Serial error:", e)
    ser = None


# đọc dữ liệu Arduino
def read_serial():
    global bpm_value, spo2_value, sensor_status, stabilization_progress, last_save_time
    global reading_start_time, session_completed
    while True:
        if ser and ser.in_waiting:
            try:
                line = ser.readline().decode().strip()
                if line:
                    if line == "Finger removed":
                        sensor_status = "waiting"
                        bpm_value = 0
                        spo2_value = 0.0
                        stabilization_progress = 0
                        reading_start_time = None
                        session_completed = False
                    elif line == "Finger detected":
                        sensor_status = "stabilizing"
                        stabilization_progress = 0
                        reading_start_time = None
                        session_completed = False
                    elif line.startswith("Stabilizing..."):
                        if not session_completed:
                            sensor_status = "stabilizing"
                        try:
                            parts = line.replace("Stabilizing...", "").strip().split("/")
                            if len(parts) == 2:
                                stabilization_progress = int(int(parts[0]) / int(parts[1]) * 100)
                        except Exception:
                            pass
                    elif line.startswith("BPM:"):
                        match_bpm = re.search(r"BPM:\s*([\d\.\-]+)", line)
                        if match_bpm and match_bpm.group(1) != "--":
                            try:
                                bpm_value = int(float(match_bpm.group(1)))
                            except ValueError:
                                pass
                        
                        match_spo2 = re.search(r"SpO2:\s*([\d\.]+)", line)
                        if match_spo2:
                            try:
                                spo2_value = float(match_spo2.group(1))
                            except ValueError:
                                pass

                        if bpm_value > 0 and spo2_value > 0:
                            if not session_completed:
                                sensor_status = "reading"
                                if reading_start_time is None:
                                    reading_start_time = time.time()
                                else:
                                    elapsed = time.time() - reading_start_time
                                    if elapsed >= 15:
                                        if "user_id" in session_cache:
                                            save_to_db(session_cache["user_id"], bpm_value, spo2_value)
                                            print(f"Logged BPM {bpm_value}, SpO2 {spo2_value} for User {session_cache['user_id']} after 15s")
                                        session_completed = True
                                        sensor_status = "completed"
            except Exception as e:
                # print("Error reading serial:", e)
                pass
        time.sleep(0.02)

# Simple cache for background thread to check login status
session_cache = {}

def save_to_db(user_id, bpm, spo2):
    with app.app_context():
        try:
            record = BpmRecord(user_id=user_id, bpm=bpm, spo2=spo2)
            db.session.add(record)
            db.session.commit()
        except Exception as e:
            print("DB Save Error:", e)

threading.Thread(target=read_serial, daemon=True).start()


@app.route("/bpm")
def bpm():
    return jsonify({
        "bpm": bpm_value,
        "spo2": spo2_value,
        "status": sensor_status,
        "progress": stabilization_progress,
        "logged_in": "user_id" in session,
        "phone": session.get("phone", "")
    })

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    phone = data.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Phone number required"}), 400
    
    user = User.query.filter_by(phone_number=phone).first()
    if not user:
        user = User(phone_number=phone)
        db.session.add(user)
        db.session.commit()
    
    session["user_id"] = user.id
    session["phone"] = phone
    session_cache["user_id"] = user.id # Update cache for bg thread
    return jsonify({"success": True, "phone": phone})

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("phone", None)
    session_cache.pop("user_id", None)
    return jsonify({"success": True})

@app.route("/history")
def history():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Not logged in"}), 401
    
    records = BpmRecord.query.filter_by(user_id=session["user_id"]).order_by(BpmRecord.timestamp.desc()).limit(20).all()
    history_data = [{"bpm": r.bpm, "spo2": r.spo2, "date": r.timestamp.strftime("%Y-%m-%d "), "time": r.timestamp.strftime("%H:%M:%S")} for r in records]
    return jsonify({"success": True, "history": history_data})


@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)