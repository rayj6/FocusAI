from flask import Flask, request, send_file, jsonify # type: ignore
from flask_cors import CORS # type: ignore
import os

app = Flask(__name__)
CORS(app) # Cho phép app mobile truy cập

PROOFS_DIR = "proofs"
if not os.path.exists(PROOFS_DIR): os.makedirs(PROOFS_DIR)

device_registry = {}

@app.route('/update_status', methods=['POST'])
def update_status():
    code = request.form.get('code')
    device_registry[code] = {
        "is_distracted": request.form.get('is_distracted') == 'True',
        "reason": request.form.get('reason', ''),
        "timestamp": request.form.get('timestamp', '')
    }
    if 'image' in request.files:
        file = request.files['image']
        file.save(os.path.join(PROOFS_DIR, f"proof_{code}.jpg"))
    return jsonify({"status": "success"})

@app.route('/status/<code>', methods=['GET'])
def get_status(code):
    return jsonify(device_registry.get(code, {"is_distracted": False}))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)