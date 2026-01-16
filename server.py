import os
import random
import string
import json
import smtplib
import time
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import firebase_admin # type: ignore
from firebase_admin import credentials, db # type: ignore
from dotenv import load_dotenv # type: ignore

# Load configuration
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# --- CONFIGURATION ---
FIREBASE_URL = os.getenv("FIREBASE_DATABASE_URL")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
SEPAY_API_KEY = os.getenv("SEPAY_API_KEY")

# --- FIREBASE INIT ---
RENDER_SECRET_PATH = "/etc/secrets/serviceAccountKey.json"
LOCAL_SECRET_PATH = "serviceAccountKey.json"
service_account_path = RENDER_SECRET_PATH if os.path.exists(RENDER_SECRET_PATH) else LOCAL_SECRET_PATH

try:
    if os.path.exists(service_account_path):
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
        print(f"✅ Firebase initialized successfully using: {service_account_path}")
except Exception as e:
    print(f"❌ Firebase Init Error: {e}")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROOFS_DIR = os.path.join(BASE_DIR, "proofs")
if not os.path.exists(PROOFS_DIR): os.makedirs(PROOFS_DIR)

# Device State (RAM)
device_registry = {}

# --- HELPERS ---
def generate_id(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def send_license_email(to_email, key, tier):
    msg = MIMEMultipart()
    msg['From'] = f"GFocus Team <{SENDER_EMAIL}>"
    msg['To'] = to_email
    msg['Subject'] = f"Your GFocus {tier} License Key"
    body = f"Mã kích hoạt của bạn: {key}\nGói: {tier}"
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    try:
        s = smtplib.SMTP("smtp.gmail.com", 587)
        s.starttls()
        s.login(SENDER_EMAIL, SENDER_PASSWORD)
        s.send_message(msg)
        s.quit()
        return True
    except: return False

def check_payment_via_sepay(transaction_note):
    SEPAY_API_URL_NEW = "https://my.sepay.vn/userapi/transactions/list"
    api_key = SEPAY_API_KEY if SEPAY_API_KEY.startswith("Bearer ") else f"Bearer {SEPAY_API_KEY}"
    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    try:
        response = requests.get(SEPAY_API_URL_NEW, headers=headers, params={"limit": 50})
        if response.status_code == 200:
            data = response.json()
            search_target = str(transaction_note).replace("-", "").replace(" ", "").upper()
            for tx in data.get("transactions", []):
                content_clean = str(tx.get("transaction_content", "")).upper().replace("-", "").replace(" ", "").replace(".", "")
                if search_target in content_clean:
                    return {"amount": float(tx.get("amount_in", 0)), "bank_ref": tx.get("id"), "paid_at": tx.get("transaction_date")}
    except: pass
    return None

# --- ADMIN ROUTES ---

@app.route('/admin/ledger', methods=['GET'])
def get_admin_ledger():
    try:
        all_tx = db.reference('transactions').get() or {}
        ledger = []
        for note, data in all_tx.items():
            ledger.append({
                "email": data.get('email'), "license_key": data.get('license_key'),
                "amount": data.get('amount_received', 0), "status": data.get('status'),
                "tier": data.get('tier'), "date": data.get('created_at', "")
            })
        return jsonify(sorted(ledger, key=lambda x: x['date'], reverse=True))
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/admin/live-rooms', methods=['GET'])
def get_live_rooms():
    rooms = []
    for code, info in device_registry.items():
        rooms.append({"code": code, "status": "Distracted" if info.get('is_distracted') else "Focused", "is_danger": info.get('is_distracted')})
    return jsonify(rooms)

# --- APP ROUTES ---

@app.route('/generate_transaction_note', methods=['GET'])
def get_note():
    plan = request.args.get('plan', 'PRO').upper()
    return jsonify({"transaction_note": f"GFOCUS-{plan}-{generate_id(6)}"})

@app.route('/confirm_transaction', methods=['POST'])
def confirm():
    data = request.json
    note, email, plan = data.get('transaction_note'), data.get('email'), data.get('plan', 'PRO').upper()
    if not note or not email: return jsonify({"error": "Missing data"}), 400
    db.reference(f'transactions/{note}').set({
        "email": email, "status": "pending", "tier": plan,
        "license_key": f"GF-{generate_id(12)}", "created_at": datetime.now().isoformat()
    })
    return jsonify({"status": "pending"})

@app.route('/check_payment_status', methods=['POST'])
def check_status():
    data = request.json
    note = data.get('transaction_note')
    REQUIRED_AMOUNT = 315000
    payment_info = check_payment_via_sepay(note)
    if payment_info:
        ref = db.reference(f'transactions/{note}')
        tx = ref.get()
        if payment_info['amount'] >= REQUIRED_AMOUNT:
            if tx.get('status') == 'pending':
                ref.update({"status": "paid", "amount_received": payment_info['amount']})
                send_license_email(tx['email'], tx['license_key'], tx['tier'])
            return jsonify({"status": "success", "license_key": tx['license_key'], "tier": tx['tier']})
    return jsonify({"status": "not_found_yet"}), 200

@app.route('/verify_license', methods=['POST'])
def verify_license():
    key = request.json.get('license_key')
    all_tx = db.reference('transactions').get() or {}
    for note, data in all_tx.items():
        if data.get('license_key') == key and data.get('status') == 'paid':
            return jsonify({"valid": True, "tier": data.get('tier')})
    return jsonify({"valid": False}), 404

# --- MONITORING ROUTES (FIXED) ---

@app.route('/update_status', methods=['POST'])
def update_status():
    code = request.form.get('code')
    is_distracted = str(request.form.get('is_distracted', 'False')).lower() in ['true', '1']
    device_registry[code] = {
        "is_distracted": is_distracted,
        "reason": request.form.get('reason', 'Focusing'),
        "timestamp": request.form.get('timestamp', ''),
        "session_id": int(request.form.get('session_id', 0)),
        "seconds": int(request.form.get('seconds', 0)) # Timer data
    }
    if 'image' in request.files and is_distracted:
        request.files['image'].save(os.path.join(PROOFS_DIR, f"proof_{code}.jpg"))
    return jsonify({"status": "success"})

@app.route('/status/<code>', methods=['GET'])
def get_status(code):
    data = device_registry.get(code, {"is_distracted": False, "reason": "Offline", "seconds": 0, "session_id": 0})

    # Determine the status string
    if data.get("reason") == "Stopped" or data.get("reason") == "Offline":
        status_str = "IDLE"
    elif data.get("is_distracted"):
        status_str = "DISTRACTED"
    else:
        status_str = "FOCUSING"

    response = {
        "status": status_str,
        "seconds": data.get("seconds", 0),
        "session_id": data.get("session_id"),
        "reason": data.get("reason", ""),
        "timestamp": data.get("timestamp", ""),
        "image_url": None
    }
    if data.get("is_distracted"):
        response["image_url"] = f"{request.host_url}proofs/proof_{code}.jpg"
    return jsonify(response)

@app.route('/proofs/<filename>')
def serve_proof_file(filename):
    """Serves the actual image file to the mobile/web app"""
    return send_from_directory(PROOFS_DIR, filename)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)