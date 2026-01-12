from flask import Flask, request, jsonify, send_from_directory # type: ignore
from flask_cors import CORS # type: ignore
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

PROOFS_DIR = "proofs"
if not os.path.exists(PROOFS_DIR): 
    os.makedirs(PROOFS_DIR)

# device_registry stores the state for each pairing code
device_registry = {}

@app.route('/update_status', methods=['POST'])
def update_status():
    code = request.form.get('code')
    # Handle various boolean formats (True, true, 1)
    raw_distracted = str(request.form.get('is_distracted', 'False')).lower()
    is_distracted = raw_distracted in ['true', '1', 'yes']
    
    # Critical: Store session_id so the mobile app knows a session is active
    device_registry[code] = {
        "is_distracted": is_distracted,
        "reason": request.form.get('reason', 'Focusing'),
        "timestamp": request.form.get('timestamp', ''),
        "session_id": int(request.form.get('session_id', 0))
    }
    
    if 'image' in request.files:
        file = request.files['image']
        file.save(os.path.join(PROOFS_DIR, f"proof_{code}.jpg"))
        
    print(f"Update for {code}: Distracted={is_distracted}, Session={device_registry[code]['session_id']}")
    return jsonify({"status": "success"})

@app.route('/status/<code>', methods=['GET'])
def get_status(code):
    # Default to IDLE (session_id: 0) if no data exists
    return jsonify(device_registry.get(code, {"is_distracted": False, "reason": "Offline", "session_id": 0}))

@app.route('/proof/<code>', methods=['GET'])
def get_proof(code):
    # Serves the image to the mobile app
    return send_from_directory(PROOFS_DIR, f"proof_{code}.jpg")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)