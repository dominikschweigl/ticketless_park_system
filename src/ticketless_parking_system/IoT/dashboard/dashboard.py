import os
import json
import base64
from typing import Set, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from nats.aio.client import Client as NATS

NATS_URL = os.environ.get("NATS_URL", "nats://localhost:4222")

app = FastAPI()


app.mount("/static", StaticFiles(directory="static"), name="static")

clients: Set[WebSocket] = set()


last_state: Dict[str, Dict[str, Any]] = {}


last_camera: Dict[str, str] = {}


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
        await ws.send_text(json.dumps({
            "type": "snapshot",
            "states": last_state,
            "cameras": last_camera,
        }))


        while True:
            await ws.receive_text()

    except WebSocketDisconnect:
        clients.discard(ws)
    except Exception:
        clients.discard(ws)


@app.on_event("startup")
async def startup():
    nc = NATS()
    await nc.connect(NATS_URL)
    app.state.nc = nc

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

    async def on_camera(msg):

        cam_id = None
        try:
            if msg.headers:
                cam_id = msg.headers.get("camera_id")  
        except Exception:
            cam_id = None

        if not cam_id:

            cam_id = msg.subject.replace("camera.", "")  

        b64 = base64.b64encode(msg.data).decode("ascii")
        data_url = f"data:image/jpeg;base64,{b64}"

        last_camera[cam_id] = data_url

        await broadcast({
            "type": "camera",
            "camera_id": cam_id,
            "jpg": data_url
        })


    await nc.subscribe("*.state", cb=on_state)


    await nc.subscribe("camera.*", cb=on_camera)


@app.on_event("shutdown")
async def shutdown():
    nc: NATS = app.state.nc
    await nc.drain()