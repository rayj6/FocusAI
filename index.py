# app.py (Server)
from flask import Flask, request, send_file, jsonify
import os

app = Flask(__name__)
PROOFS_DIR = "proofs"
if not os.path.exists(PROOFS_DIR): os.makedirs(PROOFS_DIR)

# Lưu trữ trạng thái của tất cả thiết bị đang chạy
# Cấu trúc: {"123456": {"is_distracted": False, "session_id": 123, ...}}
device_registry = {}

@app.route('/update_status', methods=['POST'])
def update_status():
    code = request.form.get('code')
    is_distracted = request.form.get('is_distracted') == 'True'
    reason = request.form.get('reason', '')
    session_id = int(request.form.get('session_id', 0))
    timestamp = request.form.get('timestamp', '')

    # Lưu trạng thái riêng cho mã code này
    device_registry[code] = {
        "is_distracted": is_distracted,
        "reason": reason,
        "session_id": session_id,
        "timestamp": timestamp
    }

    # Lưu ảnh riêng theo code: proof_123456.jpg
    if 'image' in request.files:
        file = request.files['image']
        file.save(os.path.join(PROOFS_DIR, f"proof_{code}.jpg"))

    return jsonify({"status": "success"})

@app.route('/status/<code>', methods=['GET'])
def get_status(code):
    # Chỉ trả về dữ liệu của đúng mã code yêu cầu
    status = device_registry.get(code, {"session_id": 0, "is_distracted": False})
    return jsonify(status)

@app.route('/proof/<code>', methods=['GET'])
def get_proof(code):
    # Chỉ trả về ảnh của đúng mã code yêu cầu
    path = os.path.join(PROOFS_DIR, f"proof_{code}.jpg")
    if os.path.exists(path):
        return send_file(path, mimetype='image/jpeg')
    return "Not Found", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)