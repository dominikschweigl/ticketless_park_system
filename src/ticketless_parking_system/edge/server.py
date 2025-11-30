import os
import cv2
import numpy as np
import asyncio
from nats.aio.client import Client as NATS

NATS_URL = os.environ.get("NATS_URL")

async def main():
    nc = NATS()
    await nc.connect(NATS_URL)

    async def entry_handler(msg):
        jpg = np.frombuffer(msg.data, np.uint8)
        img = cv2.imdecode(jpg, cv2.IMREAD_COLOR)
        cv2.imshow("Entry Camera", img)
        
    await nc.subscribe("camera.entry", cb=entry_handler)

    async def exit_handler(msg):
        jpg = np.frombuffer(msg.data, np.uint8)
        img = cv2.imdecode(jpg, cv2.IMREAD_COLOR)
        cv2.imshow("Exit Camera", img)
        
    await nc.subscribe("camera.exit", cb=exit_handler)

    print("Camera subscriber running...")
    while True:
        if cv2.pollKey() == 27:  # ESC key
            break
        await asyncio.sleep(1)

asyncio.run(main())
