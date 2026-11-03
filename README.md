# Nhận diện loại xe trong ảnh

Web app phân loại phương tiện giao thông: tải lên ảnh có một chiếc xe, mô hình ResNet18 cho biết đó là xe đạp, xe buýt, ô tô, xe máy hay xe tải.

## Chạy trên máy

```bash
pip install -r requirements.txt
python app.py
```

Mở http://127.0.0.1:7860

## Cấu trúc

- `app.py`: máy chủ FastAPI, nạp `best_model.pth` và trả kết quả ở `/api/predict`
- `static/`: giao diện (HTML, CSS, JS)
- `assets/`: ảnh minh họa từ Wikimedia Commons, nguồn ghi trong `assets/credits.json` và ở chân trang
- `Dockerfile`: dùng để deploy lên Render (Web Service, runtime Docker)
