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

# Tải cấu hình từ .env (cho local) hoặc Environment Variables (cho Render)
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# --- CONFIGURATION ---
FIREBASE_URL = os.getenv("FIREBASE_DATABASE_URL")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
SEPAY_API_KEY = os.getenv("SEPAY_API_KEY")
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
    """
    Truy vấn API SePay (userapi) để đối soát giao dịch dựa trên nội dung chuyển khoản.
    """
    # Cập nhật endpoint đúng theo tài liệu mới nhất
    SEPAY_API_URL_NEW = "https://my.sepay.vn/userapi/transactions/list"
    
    api_key = SEPAY_API_KEY
    if not api_key.startswith("Bearer "):
        api_key = f"Bearer {api_key}"

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }

    try:
        # Lấy 50 giao dịch gần nhất
        response = requests.get(SEPAY_API_URL_NEW, headers=headers, params={"limit": 50})
        
        if response.status_code == 200:
            data = response.json()
            transactions = data.get("transactions", [])
            
            # Chuẩn hóa mã cần tìm (Viết hoa, xóa khoảng trắng thừa)
            search_code = str(transaction_note).strip().upper()
            
            for tx in transactions:
                # SePay sử dụng 'transaction_content' cho nội dung chuyển khoản
                content = str(tx.get("transaction_content", "")).upper()
                
                # Sử dụng toán tử 'in' để tìm mã trong chuỗi dài của ngân hàng (MBVCB.125...)
                if search_code in content:
                    print(f"✅ Khớp giao dịch: {search_code}")
                    return {
                        # Tiền vào được lưu trong trường 'amount_in'
                        "amount": float(tx.get("amount_in", 0)), 
                        "bank_ref": tx.get("id"),
                        "paid_at": tx.get("transaction_date")
                    }
        else:
            print(f"❌ SePay API Error: {response.status_code}")
    except Exception as e:
        print(f"❌ SePay Connection Error: {e}")
        
    return None


# --- ADMIN DASHBOARD API ---

@app.route('/admin/stats', methods=['GET'])
def get_admin_stats():
    """Lấy số liệu thống kê tổng quát cho dashboard"""
    try:
        # 1. Tính doanh thu từ Firebase
        all_tx = db.reference('transactions').get() or {}
        total_revenue = sum(float(data.get('amount_received', 0)) for data in all_tx.values() if data.get('status') == 'paid')
        
        # 2. Đếm số người dùng (dựa trên số lượng transaction/email)
        total_users = len(set(data.get('email') for data in all_tx.values()))
        
        # 3. Trạng thái hệ thống
        active_rooms = len(device_registry)
        
        return jsonify({
            "total_revenue": total_revenue,
            "active_users": total_users,
            "active_rooms": active_rooms,
            "status": "Stable"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/live-rooms', methods=['GET'])
def get_live_rooms():
    """Lấy danh sách chi tiết các thiết bị đang online"""
    # Chuyển dictionary thành list để dễ hiển thị ở React
    rooms_list = []
    for code, info in device_registry.items():
        rooms_list.append({
            "code": code,
            "status": "Distracted" if info.get('is_distracted') else "Focused",
            "user": "User_" + code[:3], # Placeholder vì code chưa định danh user
            "is_danger": info.get('is_distracted')
        })
    return jsonify(rooms_list)

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
    """
    API để Frontend gọi kiểm tra trạng thái thanh toán.
    Hàm này sẽ gọi SePay để đối soát và cập nhật Firebase nếu thành công.
    """
    data = request.json
    note = data.get('transaction_note')
    REQUIRED_AMOUNT = 2000  # Ngưỡng thanh toán tối thiểu
    
    if not note:
        return jsonify({"error": "Note required"}), 400

    # Thực hiện đối soát với SePay
    payment_info = check_payment_via_sepay(note)
    
    if payment_info:
        amount_paid = payment_info['amount']
        ref = db.reference(f'transactions/{note}')
        tx = ref.get()
        
        if not tx:
            return jsonify({"error": "Transaction not found in system"}), 404

        # Trường hợp 1: Đủ tiền
        if amount_paid >= REQUIRED_AMOUNT:
            if tx.get('status') == 'pending':
                ref.update({
                    "status": "paid",
                    "bank_ref": payment_info['bank_ref'],
                    "amount_received": amount_paid,
                    "paid_at": payment_info['paid_at'] or datetime.now().isoformat()
                })
                # Gửi Email chứa License Key cho khách hàng
                send_license_email(tx['email'], tx['license_key'], tx['tier'])
            
            return jsonify({
                "status": "success", 
                "license_key": tx['license_key'],
                "tier": tx['tier']
            })

        # Trường hợp 2: Thiếu tiền
        else:
            return jsonify({
                "status": "failed",
                "reason": "Insufficient amount",
                "required_amount": REQUIRED_AMOUNT,
                "paid_amount": amount_paid,
                "license_key": tx['license_key'],
                "note": note
            }), 200
            
    # Trường hợp chưa thấy giao dịch
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
