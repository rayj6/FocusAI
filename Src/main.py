import cv2
import pickle
import json
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

# CẤU HÌNH SERVER
SERVER_URL = "http://172.20.10.3:5000" 

def resource_path(relative_path):
    """ Lấy đường dẫn tuyệt đối đến tài nguyên, hỗ trợ cho PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class FullScreenMonitorApp:
    def __init__(self, window):
        self.window = window
        self.window.title("GreenAI") # Đổi tiêu đề ứng dụng
        self.window.attributes('-fullscreen', True)
        self.window.configure(bg="#020617")
        
        self.engine = CrystalEngine()
        self.my_code = str(random.randint(100000, 999999))
        self.running = False
        self.is_processing_ai = False # Cờ kiểm soát luồng AI
        self.current_session_id = 0
        self.start_timestamp = 0
        self.distract_counter = 0
        self.cap = None

        # Load não bộ sử dụng resource_path
        try:
            brain_path = resource_path("Brain/crystal_brain.pb")
            with open(brain_path, 'rb') as f:
                self.vertices = pickle.load(f)['vertices']
        except Exception as e:
            print(f"Lỗi load Brain: {e}")
            self.vertices = {}

        self.setup_ui()
        self.send_to_server(False, "Stopped", 0) # Khởi tạo trạng thái dừng ban đầu
        
        # Thoát khi nhấn ESC
        self.window.bind("<Escape>", lambda e: self.on_closing())

    def setup_ui(self):
        self.top_bar = tk.Frame(self.window, bg="#0f172a", height=100)
        self.top_bar.pack(fill="x")
        
        # Hiển thị tên thương hiệu và mã Pairing
        tk.Label(self.top_bar, text=f"GreenAI • CODE: {self.my_code}", fg="#fbbf24", 
                 bg="#0f172a", font=("Inter", 20, "bold")).pack(side="left", padx=40)
        
        self.lbl_timer = tk.Label(self.top_bar, text="00:00:00", fg="#94a3b8", 
                                  bg="#0f172a", font=("Courier", 28, "bold"))
        self.lbl_timer.pack(side="right", padx=50)

        self.lbl_video = tk.Label(self.window, bg="#000")
        self.lbl_video.pack(expand=True, pady=20)

        self.btn_toggle = tk.Label(self.window, text="START MONITORING", fg="white", 
                                   bg="#059669", font=("Inter", 16, "bold"), 
                                   width=25, height=2, cursor="hand2")
        self.btn_toggle.pack(side="bottom", pady=60)
        self.btn_toggle.bind("<Button-1>", lambda e: self.toggle_session())

    def send_to_server(self, is_distracted, reason, session_id, frame=None):
        def _bg_send():
            data = {
                "code": self.my_code, # QUAN TRỌNG: Định danh thiết bị
                "is_distracted": str(is_distracted),
                "reason": reason,
                "session_id": str(session_id),
                "timestamp": datetime.now().strftime("%H:%M:%S") if is_distracted else ""
            }
            files = {}
            if frame is not None:
                _, img_encoded = cv2.imencode('.jpg', frame)
                files = {'image': ('proof.jpg', img_encoded.tobytes(), 'image/jpeg')}
            
            try:
                # Gửi đến API chung, server sẽ tự phân loại dựa vào 'code' trong data
                requests.post(f"{SERVER_URL}/update_status", data=data, files=files, timeout=1)
            except: pass
        threading.Thread(target=_bg_send, daemon=True).start().start()

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
        if self.cap:
            self.cap.release()
            self.cap = None
        self.lbl_video.config(image="")
        self.send_to_server(False, "Stopped", 0)

    def on_closing(self):
        self.stop_session()
        self.window.destroy()

    def update_loop(self):
        if self.running and self.cap:
            ret, frame = self.cap.read()
            if ret:
                # Cập nhật thời gian
                elapsed = int(time.time() - self.start_timestamp)
                self.lbl_timer.config(text=time.strftime('%H:%M:%S', time.gmtime(elapsed)))
                
                # Gọi AI xử lý nếu luồng trước đã hoàn tất
                if not self.is_processing_ai:
                    threading.Thread(target=self.check_ai, args=(frame.copy(),), daemon=True).start()
                
                # Hiển thị Video lên GUI
                img_display = cv2.cvtColor(cv2.resize(frame, (800, 450)), cv2.COLOR_BGR2RGB)
                imgtk = ImageTk.PhotoImage(image=Image.fromarray(img_display))
                self.lbl_video.imgtk = imgtk
                self.lbl_video.configure(image=imgtk)
            
            self.window.after(35, self.update_loop)

    def check_ai(self, frame):
        self.is_processing_ai = True
        try:
            # Truyền trực tiếp frame (mảng numpy) vào engine, không ghi file
            tags = self.engine._extract_features(frame)
            
            is_bad = any(t in self.vertices and ("closed" in t or "no_human" in t) for t in tags)
            if is_bad:
                self.distract_counter += 1
                if self.distract_counter == 6: # Nhận diện xao nhãng sau ~2 giây
                    self.send_to_server(True, "Distracted", self.current_session_id, frame)
            else:
                if self.distract_counter >= 6:
                    self.send_to_server(False, "Focusing", self.current_session_id)
                self.distract_counter = 0
        except Exception as e:
            print(f"AI Error: {e}")
        finally:
            self.is_processing_ai = False

if __name__ == "__main__":
    root = tk.Tk()
    app = FullScreenMonitorApp(root)
    root.mainloop()