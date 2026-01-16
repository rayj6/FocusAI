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

# --- CONFIG & CYBER PALETTE ---
# SERVER_URL = "https://focusai-18m3.onrender.com"
SERVER_URL = "http://172.20.10.3:5000"
BG_MAIN = "#050505"      # OLED Black
BG_SIDE = "#0F1115"      # Dark Slate Sidebar
ACCENT_CYAN = "#00F0FF"  # High-tech Cyan
ACCENT_RED = "#FF003C"   # Cyber Red
ACCENT_GREEN = "#10B981" # Emerald Green
TEXT_MAIN = "#E2E8F0"    # Off-white
TEXT_DIM = "#64748B"     # Muted Slate

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

class FullScreenMonitorApp:
    def __init__(self, window):
        self.window = window
        self.window.title("GFOCUS EXECUTIVE")
        self.window.attributes('-fullscreen', True)
        self.window.configure(bg=BG_MAIN)
        
        # Core Logic Components
        self.engine = CrystalEngine()
        self.my_code = str(random.randint(100000, 999999))
        self.running = False
        self.is_processing_ai = False
        self.current_session_id = 0
        self.start_timestamp = 0
        self.distract_counter = 0
        self.last_send_time = 0
        self.cap = None

        self.setup_ui()
        self.window.bind("<Escape>", lambda e: self.on_closing())

    def setup_ui(self):
        # --- LEFT SIDEBAR ---
        self.sidebar = tk.Frame(self.window, bg=BG_SIDE, width=320)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        tk.Label(self.sidebar, text="GFOCUS", fg=ACCENT_CYAN, bg=BG_SIDE, font=("Impact", 36)).pack(pady=(50, 5))
        tk.Label(self.sidebar, text="EXECUTIVE TERMINAL", fg=TEXT_DIM, bg=BG_SIDE, font=("Arial", 8, "bold")).pack()

        # Terminal Log (Complexity feature)
        self.log_box = tk.Text(self.sidebar, bg="#050505", fg=ACCENT_GREEN, font=("Courier", 10),
                               height=12, bd=0, padx=15, pady=15, state="disabled")
        self.log_box.pack(fill="x", padx=20, pady=30)
        self.add_log("System Ready...")

        # --- DOCKED CONTROLS ---
        self.controls = tk.Frame(self.sidebar, bg=BG_SIDE)
        self.controls.pack(side="bottom", fill="x", pady=50)

        tk.Label(self.controls, text="ACCESS ROOM CODE", fg=TEXT_DIM, bg=BG_SIDE, font=("Arial", 8, "bold")).pack()
        tk.Label(self.controls, text=self.my_code, fg="white", bg=BG_SIDE, font=("Courier", 26, "bold")).pack(pady=(5, 25))

        # Start/Stop Label (Mac style button)
        self.btn_toggle = tk.Label(self.controls, text="START ENGINE", fg="black", bg=ACCENT_CYAN,
                                   font=("Arial Black", 12), width=20, height=2, cursor="hand2")
        self.btn_toggle.pack(padx=20)
        self.btn_toggle.bind("<Button-1>", lambda e: self.toggle_session())

        # --- MAIN VIEWPORT ---
        self.main_view = tk.Frame(self.window, bg=BG_MAIN)
        self.main_view.pack(side="right", expand=True, fill="both")

        self.lbl_timer = tk.Label(self.main_view, text="00:00:00", fg=TEXT_DIM, bg=BG_MAIN, font=("Courier", 22, "bold"))
        self.lbl_timer.place(relx=0.96, rely=0.04, anchor="ne")

        self.video_wrap = tk.Frame(self.main_view, bg="#1E2024", padx=2, pady=2)
        self.video_wrap.place(relx=0.5, rely=0.45, anchor="center")
        
        self.lbl_video = tk.Label(self.video_wrap, bg="black", width=800, height=450)
        self.lbl_video.pack()

    def add_log(self, msg):
        self.log_box.config(state="normal")
        self.log_box.insert("end", f"> {msg}\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def toggle_session(self):
        if not self.running:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                self.add_log("CRITICAL: Camera Fail")
                return
            
            self.running = True
            self.start_timestamp = time.time()
            self.current_session_id = int(time.time())
            
            self.btn_toggle.config(text="STOP ENGINE", bg=ACCENT_RED, fg="white")
            self.video_wrap.config(bg=ACCENT_CYAN)
            self.add_log("Engine Live...")
            
            # Using your old working endpoint
            self.send_to_server(False, "Focusing", self.current_session_id)
            self.update_loop()
        else:
            self.stop_session()

    def stop_session(self):
        self.running = False
        self.btn_toggle.config(text="START ENGINE", bg=ACCENT_CYAN, fg="black")
        self.video_wrap.config(bg="#1E2024")
        if self.cap: self.cap.release()
        self.add_log("Session Ended.")
        self.send_to_server(False, "Stopped", 0)

    def update_loop(self):
        if self.running and self.cap:
            ret, frame = self.cap.read()
            if ret:
                elapsed = int(time.time() - self.start_timestamp)
                self.lbl_timer.config(text=time.strftime('%H:%M:%S', time.gmtime(elapsed)))
                
                if not self.is_processing_ai:
                    threading.Thread(target=self.check_ai, args=(frame.copy(),), daemon=True).start()
                
                # Resizing matching your old working code
                img_display = cv2.cvtColor(cv2.resize(frame, (800, 450)), cv2.COLOR_BGR2RGB)
                imgtk = ImageTk.PhotoImage(image=Image.fromarray(img_display))
                self.lbl_video.imgtk = imgtk
                self.lbl_video.configure(image=imgtk)
            
            # Use your old working interval (35ms)
            self.window.after(35, self.update_loop)

    def check_ai(self, frame):
        self.is_processing_ai = True
        try:
            tags = self.engine._extract_features(frame)
            is_bad = any(t in ["eyes_closed_or_distracted", "no_human_visible"] for t in tags)
            
            now = time.time()
            if is_bad:
                self.distract_counter += 1
                if self.distract_counter >= 6:
                    self.window.after(0, lambda: self.video_wrap.config(bg=ACCENT_RED))
                    if now - self.last_send_time > 3:
                        self.last_send_time = now
                        self.send_to_server(True, "Distracted", self.current_session_id, frame)
            else:
                self.window.after(0, lambda: self.video_wrap.config(bg=ACCENT_CYAN))
                if self.distract_counter >= 6:
                    self.send_to_server(False, "Focusing", self.current_session_id)
                    self.last_send_time = now
                self.distract_counter = 0
        finally:
            self.is_processing_ai = False

    def send_to_server(self, is_bad, reason, session_id, frame=None):
        elapsed_seconds = int(time.time() - self.start_timestamp) if self.running else 0
    
        def _bg_send():
            status_str = "True" if is_bad else "False"
            data = {
                "code": self.my_code,
                "is_distracted": status_str,
                "reason": reason,
                "session_id": session_id,
                "seconds": elapsed_seconds,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
            files = {}
            if frame is not None and is_bad:
                # Resize to make upload faster
                small_frame = cv2.resize(frame, (640, 360))
                _, img_encoded = cv2.imencode('.jpg', small_frame)
                # The key 'image' must match request.files['image'] in server.py
                files = {'image': ('image.jpg', img_encoded.tobytes(), 'image/jpeg')}
            
            try:
                # Updated to your old working endpoint: /update_status
                requests.post(f"{SERVER_URL}/update_status", data=data, files=files, timeout=10)
            except: pass

        threading.Thread(target=_bg_send, daemon=True).start()

    def on_closing(self):
        self.stop_session()
        self.window.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    # Forces standard tk button color behavior for Mac
    root.tk.call('tk', 'windowingsystem') 
    app = FullScreenMonitorApp(root)
    root.mainloop()