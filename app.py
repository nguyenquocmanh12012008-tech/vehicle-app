import html
import io
import json
import os
import time

import torch
import torch.nn as nn
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from torchvision import models, transforms

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "best_model.pth")
STATIC_DIR = os.path.join(BASE_DIR, "static")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

CLASSES = ["bicycle", "bus", "car", "motorbike", "truck"]
LABELS_VI = {
    "bicycle": "Xe đạp",
    "bus": "Xe buýt",
    "car": "Ô tô",
    "motorbike": "Xe máy",
    "truck": "Xe tải",
}

# Ảnh trên trang, mỗi ảnh chỉ có một chiếc xe: tên file -> (lớp đúng, chú thích, mô tả ảnh).
# Mô hình đọc từng ảnh khi khởi động, kết quả in lên dải màu cạnh mỗi ảnh.
GALLERY = {
    "2008-yamaha-jupiter-mx-135lc-20210916.jpg": ("motorbike", "Jupiter MX", "Xe máy Yamaha Jupiter MX màu đỏ đen dựng cạnh hàng rào"),
    "hanoi-bus-12.jpg": ("bus", "Hà Nội", "Xe buýt Hà Nội màu vàng đỏ chạy trên đường"),
    "xe-ap-the-thao.jpg": ("bicycle", "Thể thao", "Xe đạp thể thao khung vàng dựng trên nền gạch"),
    "hyundai-porter-3rd-gen.jpg": ("truck", "Porter", "Xe tải nhỏ Hyundai Porter màu xanh dương"),
    "newone-vinfast-fadil-white.jpg": ("car", "Fadil", "Ô tô VinFast Fadil màu trắng nhìn từ phía trước"),
    "honda-news-cub-c90.jpg": ("motorbike", "Cub chở báo", "Xe máy Honda Cub màu vàng có thùng chở báo"),
    "hanoi-bus-23153325710.jpg": ("bus", "Tuyến Thăng Long", "Xe buýt vàng đỏ tuyến Thăng Long dưới hàng cây Hà Nội"),
    "toyota-vios-xp150-sedan-front-view.jpg": ("car", "Toyota Vios", "Ô tô Toyota Vios màu bạc"),
    "xe-ap-cho-hang.jpg": ("bicycle", "Chở cây cảnh", "Xe đạp chở đầy chậu cây cảnh"),
    "thaco-towner-950-in-nha-trang.jpg": ("truck", "Thaco Towner", "Xe tải nhỏ Thaco Towner màu xanh ở Nha Trang"),
    "honda-super-cub-mid-year-1962.jpg": ("motorbike", "Cub 1962", "Xe máy Honda Super Cub đời 1962 màu đỏ kem"),
    "futa-city-bus-route-81-kim-long.jpg": ("bus", "Tuyến 81", "Xe buýt điện tuyến 81 màu xanh cốm ở TP.HCM"),
    "vinfast-vf6-zootopia-livery-at-gjaw-2025.jpg": ("car", "VF6", "Ô tô VinFast VF6 sơn họa tiết tại triển lãm"),
    "xe-ap-oi-271220092455.jpg": ("bicycle", "Xe đạp cũ", "Xe đạp cũ dựng trong nhà cạnh dãy ghế"),
    "newone-thaco-truck.jpg": ("truck", "Thùng kín", "Xe tải thùng kín Thaco màu đen đang dỡ hàng"),
}

# Năm cột ảnh của phần đầu trang; cột thứ ba rộng gấp đôi và chứa ô chữ "panel"
HERO_COLUMNS = [
    ["2008-yamaha-jupiter-mx-135lc-20210916.jpg", "hanoi-bus-12.jpg", "xe-ap-the-thao.jpg"],
    ["hyundai-porter-3rd-gen.jpg", "newone-vinfast-fadil-white.jpg", "honda-news-cub-c90.jpg"],
    ["hanoi-bus-23153325710.jpg", "panel", "toyota-vios-xp150-sedan-front-view.jpg"],
    ["xe-ap-cho-hang.jpg", "thaco-towner-950-in-nha-trang.jpg", "honda-super-cub-mid-year-1962.jpg", "futa-city-bus-route-81-kim-long.jpg"],
    ["vinfast-vf6-zootopia-livery-at-gjaw-2025.jpg", "xe-ap-oi-271220092455.jpg", "newone-thaco-truck.jpg"],
]
FIRST_DEMO = "honda-news-cub-c90.jpg"
# Ảnh mẫu ở bảng thử, không nằm trong phần đầu trang
SAMPLES = [
    ("california-city-bicycle-side-view.jpg", "Xe đạp phố"),
    ("futa-city-bus-route-16-kim-long.jpg", "Xe buýt tuyến 16"),
    ("newone-white-vinfast-fadil-full-option-times.jpg", "Fadil nhìn ngang"),
    ("hyundai-porter-3rd-gen.jpg", "Xe tải Porter"),
]


class VehicleNet(nn.Module):
    # Khớp với checkpoint: backbone.* (ResNet18), fc = [Dropout, Linear(512, 5)]
    def __init__(self, num_classes):
        super().__init__()
        self.backbone = models.resnet18(weights=None)
        self.backbone.fc = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(self.backbone.fc.in_features, num_classes),
        )

    def forward(self, x):
        return self.backbone(x)


# Một luồng CPU là đủ cho ResNet18 và giữ RAM thấp trên gói server miễn phí (512 MB)
torch.set_num_threads(1)

model = VehicleNet(len(CLASSES))
model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu", weights_only=True))
model.eval()
model.requires_grad_(False)

tf = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def classify(img):
    t0 = time.perf_counter()
    # Thu nhỏ ảnh trước (giữ tỉ lệ) để tiết kiệm RAM; model chỉ cần 224 × 224
    img.draft("RGB", (448, 448))
    img = img.convert("RGB")
    img.thumbnail((448, 448))
    x = tf(img).unsqueeze(0)
    t1 = time.perf_counter()
    # Giữ lại đầu ra của layer4 (512 × 7 × 7) để tính Grad-CAM từ cùng một lượt chạy.
    # Cắt đồ thị tại đây: chỉ phần sau layer4 cần gradient, nên phần backbone không tốn thêm RAM.
    acts = {}

    def keep_layer4(module, inputs, output):
        acts["a"] = output.detach().requires_grad_(True)
        return acts["a"]

    hook = model.backbone.layer4.register_forward_hook(keep_layer4)
    try:
        with torch.enable_grad():
            logits = model(x)
    finally:
        hook.remove()
    t2 = time.perf_counter()
    probs = torch.softmax(logits.detach(), dim=1)[0].tolist()
    t3 = time.perf_counter()
    top = max(range(len(CLASSES)), key=lambda i: probs[i])
    cam = grad_cam(logits, acts["a"], top)
    t4 = time.perf_counter()
    return {
        "cam": cam,
        "label": CLASSES[top],
        "label_vi": LABELS_VI[CLASSES[top]],
        "confidence": probs[top],
        "probs": [
            {"label": c, "label_vi": LABELS_VI[c], "p": p}
            for c, p in zip(CLASSES, probs)
        ],
        "timings_ms": {
            "preprocess": (t1 - t0) * 1000,
            "inference": (t2 - t1) * 1000,
            "softmax": (t3 - t2) * 1000,
            "gradcam": (t4 - t3) * 1000,
        },
    }


def grad_cam(logits, acts, class_idx):
    """Grad-CAM: trọng số mỗi kênh = trung bình gradient của điểm lớp theo kênh đó.

    Trả về lưới 7 × 7 (danh sách hàng), giá trị 0–1; trình duyệt phóng lưới này lên thành bản đồ nhiệt.
    """
    grads = torch.autograd.grad(logits[0, class_idx], acts)[0]
    weights = grads.mean(dim=(2, 3), keepdim=True)
    cam = torch.relu((weights * acts).sum(dim=1))[0].detach()
    if cam.max() > 0:
        cam = cam / cam.max()
    return [[round(v, 3) for v in row] for row in cam.tolist()]


def read_gallery():
    results = {}
    for name, (truth, caption, alt) in GALLERY.items():
        with Image.open(os.path.join(ASSETS_DIR, name)) as img:
            size = img.size
            r = classify(img)
        r["size"] = size
        r["file"] = name
        r["truth"] = truth
        r["truth_vi"] = LABELS_VI[truth]
        r["correct"] = r["label"] == truth
        r["caption"] = caption
        r["alt"] = alt
        results[name] = r
    return results


def read_credits(files):
    # Dòng ghi nguồn cho những ảnh thực sự xuất hiện trên trang, lấy từ assets/credits.json
    with open(os.path.join(ASSETS_DIR, "credits.json"), encoding="utf-8") as f:
        entries = {os.path.basename(e["file"]): e for e in json.load(f)}
    items = []
    for name in files:
        e = entries[name]
        items.append(
            f'<li><a href="{html.escape(e["page"])}">“{html.escape(e["title"])}”</a>, '
            f'{html.escape(e["creator"])}, <a href="{html.escape(e["licenseUrl"])}">{html.escape(e["license"])}</a></li>'
        )
    return "".join(items)


GALLERY_RESULTS = read_gallery()

app = FastAPI(title="Nhận diện phương tiện giao thông")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


def render_frame(name, n, panel_html):
    if name == "panel":
        return panel_html
    r = GALLERY_RESULTS[name]
    w, h = r["size"]
    loading = "" if n < 8 else ' loading="lazy"'
    pct = round(r["confidence"] * 100)
    if r["correct"]:
        reading = f'<b>{html.escape(r["label_vi"])} {pct}%</b> {html.escape(r["caption"])}'
    else:
        reading = f'<b>Đọc nhầm: {html.escape(r["label_vi"])} {pct}%</b> thật ra là {html.escape(r["truth_vi"].lower())}'
    return (
        f'<figure class="frame" style="--r:{w}/{h}" data-n="{n}">'
        f'<div class="media"><img src="/assets/{name}" alt="{html.escape(r["alt"])}" width="{w}" height="{h}"{loading}>'
        f'<canvas class="cam" data-cam="{json.dumps(r["cam"])}" data-aspect="{w / h:.4f}" aria-hidden="true"></canvas></div>'
        f'<figcaption class="strip s{n % 4 + 1}">{reading}</figcaption></figure>'
    )


def render_index():
    # Điền kết quả đọc ảnh vào trang ngay trên máy chủ, để trang vẫn đủ nội dung khi không có JavaScript
    with open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8") as f:
        page = f.read()
    start, end = page.index("<!--panel-->"), page.index("<!--/panel-->")
    panel_html = page[start:end]
    cols, n = [], 0
    for i, col in enumerate(HERO_COLUMNS):
        frames = []
        for name in col:
            frames.append(render_frame(name, n, panel_html))
            n += name != "panel"
        cols.append(f'<div class="col c{i + 1}" data-col>{"".join(frames)}</div>')
    page = page[:start] + "".join(cols) + page[end + len("<!--/panel-->"):]

    # Biểu đồ: mỗi ảnh một cột, xếp từ thấp đến cao; cột cuối dành cho ảnh của người xem
    ranked = sorted(GALLERY_RESULTS.values(), key=lambda r: r["confidence"])
    bars = []
    for i, r in enumerate(ranked):
        pct = round(r["confidence"] * 100)
        shown = " shown" if i in (0, len(ranked) - 1) else ""
        bars.append(
            f'<li class="b{shown}" style="--h:{r["confidence"]:.3f}" tabindex="0">'
            f'<span class="b-val">{pct}%</span>'
            f'<span class="b-tip">{html.escape(r["label_vi"])} {pct}%<br>{html.escape(r["caption"])}</span></li>'
        )
    bars.append('<li class="b mine" style="--h:0" data-mine><span class="b-val" data-mine-val>Ảnh của bạn</span>'
                '<span class="b-tip" data-mine-tip>Thử một ảnh để thêm cột này</span></li>')
    page = page.replace("{{chart}}", "".join(bars))

    # Ba ảnh mô hình kém chắc chắn nhất, kèm lựa chọn thứ hai của nó
    doubts = []
    for r in ranked[:3]:
        second = sorted(r["probs"], key=lambda p: p["p"], reverse=True)[1]
        verdict = "đúng" if r["correct"] else f'sai, thật ra là {r["truth_vi"].lower()}'
        doubts.append(
            f'<li data-reveal><img src="/assets/{r["file"]}" alt="{html.escape(r["alt"])}" width="160" height="120" loading="lazy">'
            f'<p><b>{html.escape(r["label_vi"])} {round(r["confidence"] * 100)}%</b> ({html.escape(verdict)}), '
            f'ngay sau là {html.escape(second["label_vi"].lower())} {round(second["p"] * 100)}%<br>'
            f'<span>{html.escape(r["caption"])}</span></p></li>'
        )
    page = page.replace("{{doubts}}", "".join(doubts))

    samples = []
    for name, caption in SAMPLES:
        samples.append(
            f'<button type="button" class="sample" data-sample="{name}" data-reveal>'
            f'<img src="/assets/{name}" alt="" width="1920" height="1440" loading="lazy">'
            f'<span>{html.escape(caption)}</span></button>'
        )
    page = page.replace("{{samples}}", "".join(samples))
    page = page.replace("{{credits}}", read_credits(dict.fromkeys(list(GALLERY) + [s[0] for s in SAMPLES])))

    first = GALLERY_RESULTS[FIRST_DEMO]
    page = page.replace("{{first_file}}", FIRST_DEMO)
    page = page.replace("{{first_alt}}", html.escape(first["alt"]))
    page = page.replace("{{first_caption}}", html.escape(first["caption"]))
    page = page.replace("{{first_label}}", html.escape(first["label_vi"]))
    page = page.replace("{{first_pct}}", str(round(first["confidence"] * 100)))
    avg = sum(r["confidence"] for r in GALLERY_RESULTS.values()) / len(GALLERY_RESULTS)
    page = page.replace("{{avg}}", str(round(avg * 100)))
    page = page.replace("{{count}}", str(len(GALLERY_RESULTS)))
    page = page.replace("{{correct}}", str(sum(r["correct"] for r in GALLERY_RESULTS.values())))
    return page


@app.get("/", response_class=HTMLResponse)
def index():
    return render_index()


@app.get("/api/gallery")
def gallery():
    return list(GALLERY_RESULTS.values())


@app.post("/api/predict")
async def predict(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "Ảnh quá lớn, tối đa 15 MB.")
    try:
        return classify(Image.open(io.BytesIO(data)))
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "Không đọc được file này. Hãy chọn ảnh JPG, PNG hoặc WebP.")


if __name__ == "__main__":
    # Trên máy: 127.0.0.1. Khi deploy (Docker), đặt HOST=0.0.0.0 để mọi người truy cập được
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 7860)))
