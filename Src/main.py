import cv2
import pickle
import os
import time
import threading
import random
import requests
import tkinter as tk
import sys
from datetime import datetime
from PIL import Image, ImageTk
from crystal_engine import CrystalEngine

SERVER_URL = "https://focusai-18m3.onrender.com" 

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

class FullScreenMonitorApp:
    def __init__(self, window):
        self.window = window
        self.window.title("GreenAI")
        self.window.attributes('-fullscreen', True)
        self.window.configure(bg="#020617")
        
        self.engine = CrystalEngine()
        self.my_code = str(random.randint(100000, 999999))
        self.running = False
        self.is_processing_ai = False
        self.current_session_id = 0
        self.start_timestamp = 0
        self.distract_counter = 0
        self.last_send_time = 0  # FIX: Prevent network spamming
        self.cap = None

        self.setup_ui()
        self.window.bind("<Escape>", lambda e: self.on_closing())

    def setup_ui(self):
        self.top_bar = tk.Frame(self.window, bg="#0f172a", height=100)
        self.top_bar.pack(fill="x")
        
        tk.Label(self.top_bar, text=f"GreenAI • PAIRING CODE: {self.my_code}", fg="#fbbf24", 
                 bg="#0f172a", font=("Inter", 20, "bold")).pack(side="left", padx=40)
        
        self.lbl_timer = tk.Label(self.top_bar, text="00:00:00", fg="#94a3b8", 
                                  bg="#0f172a", font=("Courier", 28, "bold"))
        self.lbl_timer.pack(side="right", padx=50)

        self.lbl_video = tk.Label(self.window, bg="#000")
        self.lbl_video.pack(expand=True, pady=20)

        self.btn_toggle = tk.Label(self.window, text="START MONITORING", fg="white", 
                                   bg="#059669", font=("Inter", 16, "bold"), width=25, height=2, cursor="hand2")
        self.btn_toggle.pack(side="bottom", pady=60)
        self.btn_toggle.bind("<Button-1>", lambda e: self.toggle_session())

    def send_to_server(self, is_bad, reason, session_id, frame=None):
        def _bg_send():
            status_str = "True" if is_bad else "False"
            data = {
                "code": self.my_code,
                "is_distracted": status_str,
                "reason": reason,
                "session_id": session_id,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
            files = {}
            if frame is not None and is_bad:
                # Resize image to make upload faster and prevent timeouts
                small_frame = cv2.resize(frame, (640, 360))
                _, img_encoded = cv2.imencode('.jpg', small_frame)
                files = {'image': ('image.jpg', img_encoded.tobytes(), 'image/jpeg')}
            
            try:
                # Increased timeout for Render Free Tier
                requests.post(f"{SERVER_URL}/update_status", data=data, files=files, timeout=10)
                print(f"Network: {reason} updated successfully.")
            except Exception as e:
                print(f"Network Busy/Error: {e}")

        threading.Thread(target=_bg_send, daemon=True).start()

    def check_ai(self, frame):
        self.is_processing_ai = True
        try:
            tags = self.engine._extract_features(frame)
            is_bad = any(t in ["eyes_closed_or_distracted", "no_human_visible"] for t in tags)
            
            now = time.time()
            if is_bad:
                self.distract_counter += 1
                # Trigger server after 2 seconds of distraction
                if self.distract_counter >= 6:
                    # Only send if 3 seconds have passed since last update
                    if now - self.last_send_time > 3:
                        self.last_send_time = now
                        self.send_to_server(True, "Distracted", self.current_session_id, frame)
            else:
                if self.distract_counter >= 6:
                    # Reset status on server when user returns
                    self.send_to_server(False, "Focusing", self.current_session_id)
                    self.last_send_time = now
                self.distract_counter = 0
        finally:
            self.is_processing_ai = False

    def toggle_session(self):
        if not self.running:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened(): return
            self.running = True
            self.start_timestamp = time.time()
            self.current_session_id = int(time.time())
            self.btn_toggle.config(text="STOP MONITORING", bg="#991b1b")
            self.send_to_server(False, "Focusing", self.current_session_id)
            self.update_loop()
        else:
            self.stop_session()

    def stop_session(self):
        self.running = False
        self.btn_toggle.config(text="START MONITORING", bg="#059669")
        if self.cap: self.cap.release()
        self.send_to_server(False, "Stopped", 0)

    def on_closing(self):
        self.stop_session()
        self.window.destroy()

    def update_loop(self):
        if self.running and self.cap:
            ret, frame = self.cap.read()
            if ret:
                elapsed = int(time.time() - self.start_timestamp)
                self.lbl_timer.config(text=time.strftime('%H:%M:%S', time.gmtime(elapsed)))
                
                if not self.is_processing_ai:
                    threading.Thread(target=self.check_ai, args=(frame.copy(),), daemon=True).start()
                
                img_display = cv2.cvtColor(cv2.resize(frame, (800, 450)), cv2.COLOR_BGR2RGB)
                imgtk = ImageTk.PhotoImage(image=Image.fromarray(img_display))
                self.lbl_video.imgtk = imgtk
                self.lbl_video.configure(image=imgtk)
            self.window.after(35, self.update_loop)

if __name__ == "__main__":
    root = tk.Tk()
    app = FullScreenMonitorApp(root)
    root.mainloop()