FROM python:3.11-slim

WORKDIR /app



RUN apt-get update && \
    apt-get install -y python3-tk tk && \
    apt-get clean && rm -rf /var/lib/apt/lists/*



COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

ENV BARRIER_ID=0
ENV NATS_URL=nats://nats:4222

ENTRYPOINT ["python", "barrier.py"]