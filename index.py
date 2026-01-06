from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import os, logging, io

app = Flask(__name__)
CORS(app)

# Tắt log để sạch console
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Lưu trữ trạng thái: { "123456": { "data": {...}, "image": b'...' } }
active_sessions = {}

@app.route('/update_status', methods=['POST'])
def update_status():
    data = request.form.to_dict()
    code = data.get("code")
    file = request.files.get('image')
    
    status_data = {
        "is_distracted": data.get("is_distracted") == 'True',
        "reason": data.get("reason"),
        "session_id": int(data.get("session_id", 0)),
        "timestamp": data.get("timestamp")
    }
    
    if code not in active_sessions:
        active_sessions[code] = {}
    
    active_sessions[code]["data"] = status_data
    if file:
        active_sessions[code]["image"] = file.read()
    
    return jsonify({"status": "ok"})

@app.route('/status/<code>')
def get_status(code):
    session = active_sessions.get(code)
    if session and "data" in session:
        return jsonify(session["data"])
    return jsonify({"reason": "Stopped", "session_id": 0}), 404

@app.route('/proof/<code>')
def get_proof(code):
    session = active_sessions.get(code)
    if session and "image" in session:
        return send_file(io.BytesIO(session["image"]), mimetype='image/jpeg', max_age=0)
    return "No image", 404

if __name__ == '__main__':
    print("🚀 Multi-user Server running on port 5000")
    app.run(host='0.0.0.0', port=5000, threaded=True)