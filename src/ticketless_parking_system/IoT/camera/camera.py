import os
import cv2
import numpy as np
import asyncio
import glob
from nats.aio.client import Client as NATS

DISPLAY_TIME = 5.0
FRAME_DELAY = 1.0
NATS_URL = os.environ.get("NATS_URL")
CAMERA_ID = os.environ.get("CAMERA_ID", "0")


# ---------------------------------------------------------
# ENTRY CAMERA STREAM
# ---------------------------------------------------------
async def simulate_entry_stream(car_paths, nats_client, empty_path, entered_queue: asyncio.Queue):

    headers = {"camera_id": f"entry_{CAMERA_ID}"}

    empty_frame = cv2.imread(empty_path)
    if empty_frame is None:
        raise ValueError("Missing Empty.png")

    car_index = 0

    while True:
        # Load next car image
        car_path = car_paths[car_index]
        frame = cv2.imread(car_path)
        if frame is None:
            raise ValueError(f"Could not load {car_path}")

        print(f"[ENTRY] Car enters: {car_path}")

        # Push the frame to the exit stream
        await entered_queue.put(frame.copy())

        # --- Show car for DISPLAY_TIME ---
        start = asyncio.get_running_loop().time()
        while asyncio.get_running_loop().time() - start < DISPLAY_TIME:
            _, buf = cv2.imencode(".jpg", frame)
            await nats_client.publish("camera.entry", buf.tobytes(), headers=headers)
            await asyncio.sleep(FRAME_DELAY)

        # --- Show empty street for DISPLAY_TIME ---
        print("[ENTRY] Empty street")

        start = asyncio.get_running_loop().time()
        while asyncio.get_running_loop().time() - start < DISPLAY_TIME:
            _, buf = cv2.imencode(".jpg", empty_frame)
            await nats_client.publish("camera.entry", buf.tobytes(), headers=headers)
            await asyncio.sleep(FRAME_DELAY)

        car_index = (car_index + 1) % len(car_paths)


# ---------------------------------------------------------
# EXIT CAMERA STREAM
# ---------------------------------------------------------
async def simulate_exit_stream(nats_client, empty_path, entered_queue: asyncio.Queue):

    headers = {"camera_id": f"exit_{CAMERA_ID}"}

    empty_frame = cv2.imread(empty_path)
    if empty_frame is None:
        raise ValueError("Missing Empty.png")
    
    frames_per_car = 2 * DISPLAY_TIME * FRAME_DELAY
    exit_probability = 0.5 * 1/frames_per_car
    print(f"[EXIT] Exit probability: {exit_probability}.")

    while True:
        # Wait until entry stream provides a new car
        if entered_queue.empty() or np.random.random() > exit_probability:
            _, buf = cv2.imencode(".jpg", empty_frame)

            await nats_client.publish("camera.exit", buf.tobytes(), headers=headers)
            await asyncio.sleep(FRAME_DELAY)

        else:
            frame = await entered_queue.get()
            print("[EXIT] Car exits")
            print(f"[EXIT] {entered_queue.qsize()} inside the park.")

            # Show this car for DISPLAY_TIME
            start = asyncio.get_running_loop().time()
            while asyncio.get_running_loop().time() - start < DISPLAY_TIME:
                _, buf = cv2.imencode(".jpg", frame)

                await nats_client.publish("camera.exit", buf.tobytes(), headers=headers)
                await asyncio.sleep(FRAME_DELAY)
            


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
async def main():
    nc = NATS()
    await nc.connect(NATS_URL)

    car_paths = sorted(glob.glob("./data/Cars*.png"))
    empty_path = "./data/Empty.png"

    if not car_paths:
        raise ValueError("No car images found in ./data (Cars*.png)")

    # Queue shared between entry and exit streams
    entered_queue = asyncio.Queue()

    entry_task = asyncio.create_task(
        simulate_entry_stream(car_paths, nc, empty_path, entered_queue)
    )

    exit_task = asyncio.create_task(
        simulate_exit_stream(nc, empty_path, entered_queue)
    )

    await asyncio.gather(entry_task, exit_task)


asyncio.run(main())
