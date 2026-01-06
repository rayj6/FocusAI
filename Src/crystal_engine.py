import numpy as np # type: ignore
import os
import re
import pickle
import cv2 # type: ignore
from collections import defaultdict

class CrystalEngine:
    def __init__(self):
        self.vertices = {} 
        self.edges = {}
        self.domain_vectors = {}
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.jfif'}
        # Load bộ nhận diện một lần duy nhất khi khởi tạo
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

    def _extract_features(self, img_input):
        """
        img_input: Có thể là đường dẫn file (string) hoặc mảng numpy (frame)
        """
        # Kiểm tra nếu đầu vào là đường dẫn thì mới đọc file
        if isinstance(img_input, str):
            img = cv2.imread(img_input)
        else:
            img = img_input

        if img is None or img.size == 0:
            return []

        # Chuyển xám để xử lý AI
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Nhận diện mặt với tham số minSize để tránh lỗi scaleIdx
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(80, 80))
        
        tags = ["visual_input"]
        if len(faces) > 0:
            tags.append("face_found")
            for (x, y, w, h) in faces:
                # Cắt vùng khuôn mặt để tìm mắt (giảm tải tính toán)
                roi_gray = gray[y:y+h, x:x+w]
                # Nhận diện mắt với độ chính xác cao hơn
                eyes = self.eye_cascade.detectMultiScale(roi_gray, 1.1, 10, minSize=(20, 20))
                
                if len(eyes) >= 2:
                    tags.append("eyes_open")
                else:
                    tags.append("eyes_closed_or_distracted")
        else:
            tags.append("no_human_visible")
            
        return tags
    
    def process_training(self, data_path, progress_callback):
        all_files = [f for f in os.listdir(data_path)]
        for index, filename in enumerate(all_files):
            # Sửa domain: focus_1.jfif -> domain 'focus'
            domain = filename.split('_')[0] if '_' in filename else filename.split('.')[0]
            file_path = os.path.join(data_path, filename)
            ext = os.path.splitext(filename)[1].lower()

            words = self._extract_features(file_path) if ext in self.image_extensions else []
            if not words: # Nếu là file text nhãn
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        words = f.read().lower().split()
                except: continue

            # Logic kết tinh hình học (Giữ nguyên như bản cũ của bạn)
            if domain not in self.domain_vectors:
                v = np.random.uniform(-1, 1, 3)
                self.domain_vectors[domain] = v / np.linalg.norm(v)
            
            d_vec = self.domain_vectors[domain]
            for i in range(len(words)-1):
                w1, w2 = words[i], words[i+1]
                if w1 not in self.vertices: self.vertices[w1] = np.random.normal(0, 5, 3)
                if w2 not in self.vertices: self.vertices[w2] = self.vertices[w1] + (d_vec * 2.0)
                eid = f"{w1}<->{w2}" if w1 < w2 else f"{w2}<->{w1}"
                self.edges[eid] = self.edges.get(eid, 0) + 0.1

            progress_callback(f"Kết tinh: {filename}", int((index+1)/len(all_files)*100), len(self.vertices), len(self.edges))
        self.save_all()
        
    def save_all(self):
        brain_dir = "./Brain"
        if not os.path.exists(brain_dir): os.makedirs(brain_dir)
        
        # Lưu dữ liệu nhị phân
        with open(os.path.join(brain_dir, "crystal_brain.pb"), 'wb') as f:
            pickle.dump({"vertices": self.vertices, "edges": self.edges}, f)
        
        # Xuất file 3D để quan sát vùng xao nhãng
        self.export_to_obj(os.path.join(brain_dir, "knowledge_map.obj"))

    def export_to_obj(self, filename):
        if not self.vertices: return
        with open(filename, 'w', buffering=1024*1024*10) as f:
            f.write("# Crystal Engine 3D Knowledge Map\n")
            word_to_id = {}
            idx = 1
            for word, coord in self.vertices.items():
                word_to_id[word] = idx
                f.write(f"v {coord[0]:.4f} {coord[1]:.4f} {coord[2]:.4f}\n")
                idx += 1
            for edge_id in self.edges.keys():
                w1, w2 = edge_id.split("<->")
                if w1 in word_to_id and w2 in word_to_id:
                    f.write(f"l {word_to_id[w1]} {word_to_id[w2]}\n")