FROM python:3.11-slim

WORKDIR /app

# Bản PyTorch chỉ chạy CPU: nhẹ hơn nhiều so với bản GPU và đủ cho ResNet18
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV HOST=0.0.0.0 \
    PORT=7860
EXPOSE 7860

CMD ["python", "app.py"]
