FROM python:3.11-slim

WORKDIR /app


RUN pip install --no-cache-dir fastapi "uvicorn[standard]" nats-py


COPY dashboard.py /app/dashboard.py
COPY static/ /app/static/

ENV NATS_URL=nats://nats:4222
EXPOSE 8000

CMD ["uvicorn", "dashboard:app", "--host", "0.0.0.0", "--port", "8000"]
