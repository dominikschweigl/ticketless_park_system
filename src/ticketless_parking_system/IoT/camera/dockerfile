FROM python:3.11-slim

WORKDIR /app

# Install Debian libs needed by OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && apt-get clean

# Copy project files
COPY . /app

ENV CAMERA_ID=0

# Install Python dependencies
RUN pip install -r requirements.txt

CMD ["python", "camera.py"]
