import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# --- CẬP NHẬT CONFIG THEO DOCS MỚI ---
SEPAY_API_KEY = os.getenv("SEPAY_API_KEY") 
# URL đúng phải có chữ 'userapi'
SEPAY_API_URL = "https://my.sepay.vn/userapi/transactions/list"

def test_check_payment(transaction_note):
    print(f"--- Bắt đầu kiểm tra SePay (Docs mới) ---")
    print(f"Mã cần tìm: {transaction_note}")
    
    # Kiểm tra Bearer token
    api_key = SEPAY_API_KEY if SEPAY_API_KEY.startswith("Bearer ") else f"Bearer {SEPAY_API_KEY}"
    
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }

    try:
        # Gọi API với URL mới
        response = requests.get(SEPAY_API_URL, headers=headers, params={"limit": 20})
        
        print(f"Trạng thái HTTP: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            # Theo docs, danh sách nằm trong key 'transactions'
            transactions = data.get("transactions", [])
            print(f"Lấy được {len(transactions)} giao dịch gần nhất.\n")
            
            search_code = transaction_note.strip().upper()
            found = False
            
            for tx in transactions:
                # Quan trọng: Docs mới dùng 'transaction_content'
                content = str(tx.get("transaction_content", "")).upper()
                print(f"Đang kiểm tra nội dung: {content}")
                
                if search_code in content:
                    print(f"\n✅ KHỚP GIAO DỊCH!")
                    print(f"ID: {tx.get('id')}")
                    print(f"Ngày: {tx.get('transaction_date')}")
                    print(f"Tiền vào (amount_in): {tx.get('amount_in')}")
                    print(f"Nội dung đầy đủ: {tx.get('transaction_content')}")
                    found = True
                    break
            
            if not found:
                print(f"\n❌ Không tìm thấy giao dịch nào chứa: {transaction_note}")
        else:
            print(f"❌ Lỗi API: {response.text}")

    except Exception as e:
        print(f"❌ Lỗi kết nối: {e}")

if __name__ == "__main__":
    # Thay bằng mã thực tế bạn thấy trên Dashboard để test
    target_note = "GFOCUS PRO S503V6" 
    test_check_payment(target_note)