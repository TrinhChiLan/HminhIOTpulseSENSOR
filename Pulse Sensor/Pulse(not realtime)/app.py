from flask import Flask, jsonify, render_template, send_from_directory, request, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import serial
import threading
import time
import os
from dotenv import load_dotenv

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
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Ensure tables are created
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print("Database error:", e)

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory('assets', filename)

bpm_value = 0
last_save_time = 0

# mở serial
try:
    ser = serial.Serial('/dev/ttyACM0', 115200, timeout=0.1)
    time.sleep(2)
    ser.reset_input_buffer()
    print("Serial connected")
except Exception as e:
    print("Serial error:", e)
    ser = None


# đọc dữ liệu Arduino
def read_serial():
    global bpm_value, last_save_time
    while True:
        if ser and ser.in_waiting:
            try:
                line = ser.readline().decode().strip()
                if line:
                    bpm = int(line)
                    bpm_value = bpm
                    
                    # Logging logic: Save every 60 seconds if a user is logged in
                    current_time = time.time()
                    if "user_id" in session_cache and (current_time - last_save_time) > 60:
                        save_to_db(session_cache["user_id"], bpm)
                        last_save_time = current_time
                        print(f"Logged BPM {bpm} for User {session_cache['user_id']}")
            except Exception as e:
                # print("Error reading serial:", e)
                pass
        time.sleep(0.02)

# Simple cache for background thread to check login status
session_cache = {}

def save_to_db(user_id, bpm):
    with app.app_context():
        try:
            record = BpmRecord(user_id=user_id, bpm=bpm)
            db.session.add(record)
            db.session.commit()
        except Exception as e:
            print("DB Save Error:", e)

threading.Thread(target=read_serial, daemon=True).start()


@app.route("/bpm")
def bpm():
    return jsonify({
        "bpm": bpm_value,
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
    history_data = [{"bpm": r.bpm, "date": r.timestamp.strftime("%Y-%m-%d "), "time": r.timestamp.strftime("%H:%M:%S")} for r in records]
    return jsonify({"success": True, "history": history_data})


@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)