import os
import random
import string
import json
import smtplib
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv

# Tải cấu hình từ .env (cho local) hoặc Environment Variables (cho Render)
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# --- CONFIGURATION ---
FIREBASE_URL = os.getenv("FIREBASE_DATABASE_URL")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
SEPAY_API_KEY = os.getenv("SEPAY_API_KEY") # Phải có chữ "Bearer " phía trước
SEPAY_API_URL = "https://my.sepay.vn/api/transactions/list"

# --- KHỞI TẠO FIREBASE (FIXED CHO RENDER SECRETS) ---
# Render mặc định mount secret files vào /etc/secrets/
RENDER_SECRET_PATH = "/etc/secrets/serviceAccountKey.json"
LOCAL_SECRET_PATH = "serviceAccountKey.json"

# Kiểm tra đường dẫn nào tồn tại thì sử dụng
service_account_path = RENDER_SECRET_PATH if os.path.exists(RENDER_SECRET_PATH) else LOCAL_SECRET_PATH

try:
    if os.path.exists(service_account_path):
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
        print(f"✅ Firebase initialized successfully using: {service_account_path}")
    else:
        print(f"❌ Error: {service_account_path} not found. Check Render Secret Files.")
except Exception as e:
    print(f"❌ Firebase Init Error: {e}")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROOFS_DIR = os.path.join(BASE_DIR, "proofs")
if not os.path.exists(PROOFS_DIR): os.makedirs(PROOFS_DIR)

# Lưu trạng thái live của thiết bị (RAM)
device_registry = {}

# --- HELPERS ---
def generate_id(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def send_license_email(to_email, key, tier):
    msg = MIMEMultipart()
    msg['From'] = f"GFocus Team <{SENDER_EMAIL}>"
    msg['To'] = to_email
    msg['Subject'] = f"🔑 Your GFocus {tier} License Key"
    
    body = f"""
    Chào bạn, thanh toán của bạn đã được xác nhận thành công!
    
    Gói dịch vụ: {tier}
    Mã kích hoạt (License Key): {key}
    
    Vui lòng nhập mã này vào ứng dụng GFocus Mobile để mở khóa tính năng.
    Trân trọng,
    GFocus Team.
    """
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    try:
        s = smtplib.SMTP("smtp.gmail.com", 587)
        s.starttls()
        s.login(SENDER_EMAIL, SENDER_PASSWORD)
        s.send_message(msg)
        s.quit()
        return True
    except Exception as e:
        print(f"Mail Error: {e}")
        return False

def check_payment_via_sepay(transaction_note):
    """Truy vấn trực tiếp API SePay để đối soát giao dịch"""
    headers = {
        "Authorization": SEPAY_API_KEY, 
        "Content-Type": "application/json"
    }
    try:
        # Lấy 20 giao dịch gần nhất từ SePay API
        response = requests.get(SEPAY_API_URL, headers=headers, params={"limit": 20})
        if response.status_code == 200:
            data = response.json()
            transactions = data.get("transactions", [])
            for tx in transactions:
                # Tìm mã ghi chú GF-XXXX trong nội dung chuyển khoản
                if transaction_note in str(tx.get("content", "")):
                    return {
                        "amount": tx.get("transfer_amount"),
                        "bank_ref": tx.get("transaction_id")
                    }
    except Exception as e:
        print(f"SePay API Connection Error: {e}")
    return None

# --- API ROUTES ---

@app.route('/generate_transaction_note', methods=['GET'])
def get_note():
    """Tạo mã nội dung chuyển khoản cho khách hàng"""
    plan = request.args.get('plan', 'PRO').upper()
    note = f"GFOCUS-{plan}-{generate_id(6)}"
    return jsonify({"transaction_note": note})

@app.route('/confirm_transaction', methods=['POST'])
def confirm():
    """Lưu yêu cầu đang chờ (Pending) vào Firebase"""
    data = request.json
    note = data.get('transaction_note')
    email = data.get('email')
    plan = data.get('plan', 'PRO').upper()

    if not note or not email:
        return jsonify({"error": "Missing email or transaction note"}), 400

    ref = db.reference(f'transactions/{note}')
    ref.set({
        "email": email,
        "status": "pending",
        "tier": plan,
        "license_key": f"GF-{generate_id(12)}",
        "created_at": datetime.now().isoformat()
    })
    return jsonify({"status": "pending"})

@app.route('/check_payment_status', methods=['POST'])
def check_status():
    """Chủ động đối soát với SePay và nâng cấp tài khoản"""
    data = request.json
    note = data.get('transaction_note')
    
    if not note:
        return jsonify({"error": "Note required"}), 400

    # 1. Kiểm tra tiền qua API SePay
    payment_info = check_payment_via_sepay(note)
    
    if payment_info:
        ref = db.reference(f'transactions/{note}')
        tx = ref.get()
        
        # 2. Nếu tìm thấy giao dịch hợp lệ và đang chờ
        if tx and tx.get('status') == 'pending':
            ref.update({
                "status": "paid",
                "bank_ref": payment_info['bank_ref'],
                "amount_received": payment_info['amount'],
                "paid_at": datetime.now().isoformat()
            })
            # 3. Gửi Email License ngay lập tức
            send_license_email(tx['email'], tx['license_key'], tx['tier'])
            
            return jsonify({
                "status": "success", 
                "license_key": tx['license_key'],
                "tier": tx['tier']
            })
            
    return jsonify({"status": "not_found_yet"}), 200

@app.route('/verify_license', methods=['POST'])
def verify_license():
    """Mobile App gọi để kích hoạt tính năng"""
    key = request.json.get('license_key')
    all_tx = db.reference('transactions').get()
    if all_tx:
        for note, data in all_tx.items():
            if data.get('license_key') == key and data.get('status') == 'paid':
                return jsonify({"valid": True, "tier": data.get('tier')})
    return jsonify({"valid": False}), 404

# --- TRACKING ROUTES ---

@app.route('/update_status', methods=['POST'])
def update_status():
    """Cập nhật dữ liệu từ App Desktop/Python"""
    code = request.form.get('code')
    is_distracted = str(request.form.get('is_distracted', 'False')).lower() in ['true', '1']
    device_registry[code] = {
        "is_distracted": is_distracted,
        "reason": request.form.get('reason', 'Focusing'),
        "timestamp": request.form.get('timestamp', ''),
        "session_id": int(request.form.get('session_id', 0))
    }
    if 'image' in request.files and is_distracted:
        request.files['image'].save(os.path.join(PROOFS_DIR, f"proof_{code}.jpg"))
    return jsonify({"status": "success"})

@app.route('/status/<code>', methods=['GET'])
def get_status(code):
    return jsonify(device_registry.get(code, {"is_distracted": False, "reason": "Offline", "session_id": 0}))

@app.route('/proof/<code>', methods=['GET'])
def get_proof(code):
    return send_from_directory(PROOFS_DIR, f"proof_{code}.jpg")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
