FROM python:3.11-slim

WORKDIR /app

# Install OS dependencies needed for OpenCV or other scientific libs
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    curl \
    ca-certificates \
    sqlite3 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv (more stable download than pip for large packages)
RUN curl -fsSL https://astral.sh/uv/install.sh | sh

# Add uv to PATH
ENV PATH="/root/.local/bin:${PATH}"

# Increase download timeout for large packages like ultralytics
ENV UV_HTTP_TIMEOUT=300

# Install dependencies
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Create a directory for SQLite DB and other persisted data
RUN mkdir -p /app/dat

ENV DETECTION_MODEL_PATH=/app/models/yolov11s-license-plate.pt

RUN mkdir -p /app/models && \
    curl -L \
    https://huggingface.co/morsetechlab/yolov11-license-plate-detection/resolve/main/license-plate-finetune-v1s.pt \
    -o $DETECTION_MODEL_PATH

# Copy app
COPY . .

CMD ["python", "server.py"]
