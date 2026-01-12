from flask import Flask, request, jsonify # type: ignore
from flask_cors import CORS # type: ignore
import os

app = Flask(__name__)
# Permit all origins for mobile/desktop flexibility
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

PROOFS_DIR = "proofs"
if not os.path.exists(PROOFS_DIR): 
    os.makedirs(PROOFS_DIR)

device_registry = {}

@app.route('/update_status', methods=['POST'])
def update_status():
    code = request.form.get('code')
    # Convert incoming value to a lowercase string to handle 'True', 'true', or '1'
    raw_val = str(request.form.get('is_distracted', 'False')).lower()
    is_distracted = raw_val in ['true', '1', 'yes']
    
    device_registry[code] = {
        "is_distracted": is_distracted,
        "reason": request.form.get('reason', 'Unknown'),
        "timestamp": request.form.get('timestamp', '')
    }
    
    if 'image' in request.files:
        file = request.files['image']
        file.save(os.path.join(PROOFS_DIR, f"proof_{code}.jpg"))
        
    print(f"DEBUG: Code {code} updated. Distracted: {is_distracted}") # Check Render logs for this
    return jsonify({"status": "success"})

@app.route('/status/<code>', methods=['GET'])
def get_status(code):
    # If the code isn't in the registry, return a default safe state
    return jsonify(device_registry.get(code, {"is_distracted": False, "reason": "No data"}))

if __name__ == '__main__':
    # Use environment PORT for Render compatibility
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)