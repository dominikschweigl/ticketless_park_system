import os
import json
from typing import Set, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from nats.aio.client import Client as NATS

NATS_URL = os.environ.get("NATS_URL", "nats://localhost:4222")

app = FastAPI()

# Serve frontend + images from ./static
app.mount("/static", StaticFiles(directory="static"), name="static")

clients: Set[WebSocket] = set()
last_state: Dict[str, Dict[str, Any]] = {}  # barrier_id -> last payload


async def broadcast(payload: dict):
    data = json.dumps(payload)
    dead = []
    for ws in clients:
        try:
            await ws.send_text(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)

    try:
        await ws.send_text(json.dumps({"type": "snapshot", "states": last_state}))
        while True:
            # client may send pings; ignore
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)
    except Exception:
        clients.discard(ws)


@app.on_event("startup")
async def startup():
    app.state.nc = NATS()
    await app.state.nc.connect(NATS_URL)

    async def on_state(msg):
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return

        barrier_id = payload.get("barrier_id") or msg.subject.replace(".state", "")
        payload["barrier_id"] = barrier_id
        payload["type"] = "update"

        last_state[barrier_id] = payload
        await broadcast(payload)

    # subscribe to barriers like 0_entry.state, barrier0.state
    await app.state.nc.subscribe("*.state", cb=on_state)


@app.on_event("shutdown")
async def shutdown():
    nc: NATS = app.state.nc
    await nc.drain()
