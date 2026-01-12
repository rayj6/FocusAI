import eel # type: ignore
import threading
import time
from app_server import app as flask_app # type: ignore # Import flask app để chạy chung

eel.init('web')

# Hàm chạy Flask trong một luồng riêng
def run_flask():
    flask_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

@eel.expose
def get_system_status():
    return "AI Crystal Engine: ONLINE"

if __name__ == "__main__":
    # Chạy Flask Server ở background
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    # Chạy Dashboard Eel ở foreground
    print("Dashboard đang khởi động tại http://localhost:8000")
    eel.start('index.html', size=(1000, 800))