"""Dựng bản web tĩnh vào thư mục site/ để deploy lên Vercel.

Bản tĩnh không cần máy chủ Python: mô hình ONNX chạy ngay trong trình duyệt bằng onnxruntime-web.
Kết quả đọc 15 ảnh ở đầu trang được tính sẵn ở đây (bằng PyTorch) và ghi thẳng vào HTML.

Chạy:  python build_static.py
"""
import json
import os
import shutil

import app

SITE_DIR = os.path.join(app.BASE_DIR, "site")
ONNX_FILE = "vehicle_resnet18.onnx"
ORT_VERSION = "1.20.1"
ORT_CDN = f"https://cdn.jsdelivr.net/npm/onnxruntime-web@{ORT_VERSION}/dist/"

# Câu chữ nói về máy chủ được đổi cho đúng với bản chạy trong trình duyệt
STATIC_COPY = {
    "Đầu tiên, ảnh đi từ máy bạn lên máy chủ.": "Đầu tiên, trình duyệt mở ảnh ngay trên máy bạn.",
    "Tuỳ tốc độ mạng": "Vài mili giây",
    "Ảnh chỉ dùng để dự đoán, không được lưu lại.": "Mô hình chạy ngay trong trình duyệt, ảnh không rời khỏi máy bạn.",
    "đọc khi máy chủ khởi động.": "đọc sẵn khi dựng trang.",
}


def build():
    if os.path.isdir(SITE_DIR):
        shutil.rmtree(SITE_DIR)
    os.makedirs(os.path.join(SITE_DIR, "assets"))
    os.makedirs(os.path.join(SITE_DIR, "model"))

    page = app.render_index()
    for old, new in STATIC_COPY.items():
        if old not in page:
            raise SystemExit(f"Không tìm thấy câu cần đổi: {old}")
        page = page.replace(old, new)

    config = {
        "url": f"/model/{ONNX_FILE}",
        "wasm": ORT_CDN,
        "classes": app.CLASSES,
        "labels": app.LABELS_VI,
        "gallery": list(app.GALLERY_RESULTS.values()),
    }
    head = (
        f'<script src="{ORT_CDN}ort.min.js"></script>\n'
        f"<script>window.VEHICLE_MODEL = {json.dumps(config, ensure_ascii=False)};</script>\n"
    )
    page = page.replace('<script src="/static/main.js" defer></script>', head + '<script src="/static/main.js" defer></script>')
    with open(os.path.join(SITE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)

    shutil.copytree(app.STATIC_DIR, os.path.join(SITE_DIR, "static"), ignore=shutil.ignore_patterns("index.html"))
    used = dict.fromkeys(list(app.GALLERY) + [name for name, _ in app.SAMPLES])
    for name in used:
        shutil.copy2(os.path.join(app.ASSETS_DIR, name), os.path.join(SITE_DIR, "assets", name))
    shutil.copy2(os.path.join(app.BASE_DIR, "model", ONNX_FILE), os.path.join(SITE_DIR, "model", ONNX_FILE))
    shutil.copy2(os.path.join(app.BASE_DIR, "vercel.json"), os.path.join(SITE_DIR, "vercel.json"))

    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(SITE_DIR) for f in fs)
    print(f"Đã dựng {SITE_DIR}: {len(used)} ảnh, tổng {size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    build()
