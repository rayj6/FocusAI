from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory # type: ignore
from flask_cors import CORS # type: ignore
import os
import json
import uuid
import string
import random

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

PROOFS_DIR = "proofs"
if not os.path.exists(PROOFS_DIR): 
    os.makedirs(PROOFS_DIR)

# device_registry stores the state for each pairing code
device_registry = {}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROOFS_DIR = os.path.join(BASE_DIR, "proofs")

if not os.path.exists(PROOFS_DIR): 
    os.makedirs(PROOFS_DIR)

@app.route('/update_status', methods=['POST'])
def update_status():
    code = request.form.get('code')
    # Better boolean handling
    is_distracted = str(request.form.get('is_distracted', 'False')).lower() in ['true', '1']
    
    device_registry[code] = {
        "is_distracted": is_distracted,
        "reason": request.form.get('reason', 'Focusing'),
        "timestamp": request.form.get('timestamp', ''),
        "session_id": int(request.form.get('session_id', 0))
    }
    
    if 'image' in request.files and is_distracted:
        file = request.files['image']
        file.save(os.path.join(PROOFS_DIR, f"proof_{code}.jpg"))
        
    return jsonify({"status": "success"})

@app.route('/status/<code>', methods=['GET'])
def get_status(code):
    # Default to IDLE (session_id: 0) if no data exists
    return jsonify(device_registry.get(code, {"is_distracted": False, "reason": "Offline", "session_id": 0}))

@app.route('/proof/<code>', methods=['GET'])
def get_proof(code):
    # Serves the image to the mobile app
    return send_from_directory(PROOFS_DIR, f"proof_{code}.jpg")

TRANSACTIONS_FILE = os.path.join(BASE_DIR, "transactions.json")

def generate_random_code(length=6):
    """Tạo chuỗi ngẫu nhiên cho mã giao dịch hoặc license"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def save_transaction(data):
    """Lưu dữ liệu vào file JSON (tự động tạo nếu chưa có)"""
    transactions = []
    if os.path.exists(TRANSACTIONS_FILE):
        with open(TRANSACTIONS_FILE, 'r', encoding='utf-8') as f:
            try:
                transactions = json.load(f)
            except json.JSONDecodeError:
                transactions = []
    
    transactions.append(data)
    with open(TRANSACTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(transactions, f, indent=4)

@app.route('/generate_transaction_note', methods=['GET'])
def get_note():
    """Tạo mã ghi chú chuyển khoản cho Frontend"""
    plan = request.args.get('plan', 'PRO').upper()
    note = f"GFOCUS-{plan}-{generate_random_code()}"
    return jsonify({"transaction_note": note})

@app.route('/confirm_transaction', methods=['POST'])
def confirm_transaction():
    """Lưu thông tin khi người dùng nhấn 'Done' trên website"""
    data = request.json
    email = data.get('email')
    note = data.get('transaction_note')
    
    if not email or not note:
        return jsonify({"status": "error", "message": "Missing info"}), 400

    new_tx = {
        "email": email,
        "transaction_note": note,
        "status": "pending", # Sẽ chuyển thành 'paid' sau khi bạn check bank
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "license_key": f"GF-{generate_random_code(12)}" # Tạo sẵn license để gửi sau
    }
    
    save_transaction(new_tx)
    return jsonify({"status": "received", "message": "Verification in progress. Check email soon."})
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)