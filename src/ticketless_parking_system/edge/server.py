import os
import json
import cv2
import numpy as np
import asyncio
import sqlite3
import os
from nats.aio.client import Client as NATS
from ultralytics import YOLO
from datetime import datetime
import easyocr
from edge_db import ParkingDatabase
from nats import errors as nats_errors


from cloud_parking_client import CloudParkingClient
from parkinglot_tracker import ParkingLotTracker

DETECTION_MODEL_PATH = os.environ.get("DETECTION_MODEL_PATH")
DB_PATH = os.environ.get("DB_PATH", "parking.db")
CAR_PARK_ID = os.environ.get("CAR_PARK_ID", "lot-01")
CAR_PARK_CAPACITY = int(os.environ.get("CAR_PARK_CAPACITY", "67"))
CLOUD_URL = os.environ.get("CLOUD_URL", "http://parking-system-cloud:8080")
CAR_PARK_LAT = float(os.environ.get("CAR_PARK_LAT", "47.264947230784486"))
CAR_PARK_LNG = float(os.environ.get("CAR_PARK_LNG", "11.343537320891627"))

# NATS URLs: separate local (edge) vs cloud
EDGE_NATS_URL = os.environ.get("EDGE_NATS_URL", "nats://localhost:4222")
CLOUD_NATS_URL = os.environ.get("CLOUD_NATS_URL", "nats://localhost:4222")

async def open_barrier(nc_edge: NATS, barrier_id: str):
    subject = f"{barrier_id}.trigger"
    try:
        reply = await nc_edge.request(subject, b"", timeout=2)

        if reply.data == b"done":
            print(f"[BARRIER] Opened successfully via {subject}")
            return True
        else:
            print(f"[BARRIER] Unexpected reply from {subject}: {reply.data!r}")
            return False

    except nats_errors.NoRespondersError:
        # No barrier microservice is running -> simulate success so system keeps working
        print(f"[BARRIER][SIM] No responders on {subject}. Simulating open.")
        return True

    except asyncio.TimeoutError:
        print(f"[BARRIER] Timeout waiting for reply on {subject}.")
        return False

    except Exception as e:
        print(f"[BARRIER] Error calling {subject}: {e}")
        return False


async def checkpoint_handler(plate_text: str, id_: str, nc_edge: NATS, db: ParkingDatabase, tracker: ParkingLotTracker, cloud_client: CloudParkingClient):
    checkpoint_type = id_.split("_")[0]  # "entry" or "exit" (from camera_id)

    if checkpoint_type == "entry":
        # Check if car is already inside
        active = db.get_active_session(plate_text)
        if active:
            print(
                f"[LOGIC] Plate {plate_text} is already inside "
                f"(since {active['entry_time']}). Not creating a new session."
            )
            await open_barrier(nc_edge, id_)
        else:
            print(f"[LOGIC] Plate {plate_text} is entering. Creating new session.")
            db.register_entry(plate_text)

            # Inform cloud payment service (record entry)
            try:
                pay_res = await cloud_client.payment_car_enter(plate_text)
                print(f"[CLOUD][PAYMENT] enter recorded for {plate_text}: {pay_res}")
            except Exception as e:
                print(f"[CLOUD][PAYMENT] enter failed for {plate_text}: {e}")

            # Increment occupancy only if no booking exists
            if tracker.has_booking(plate_text):
                print(f"[BOOKING] Consuming booking for {plate_text}, not incrementing occupancy again.")
                tracker.consume_booking(plate_text)
            else:
                await tracker.increment_occupancy()
                print(f"[CLOUD] Updated occupancy to {tracker.current_occupancy}/{tracker.max_capacity}")

            await open_barrier(nc_edge, id_)

    elif checkpoint_type == "exit":
        # Check with cloud if this plate has paid
        try:
            status = await cloud_client.payment_check(plate_text)
            paid = bool(status.get("paid", False))
            price = status.get("priceCents", 0)
            print(f"[CLOUD][PAYMENT] check {plate_text}: paid={paid}, priceCents={price}")
        except Exception as e:
            print(f"[CLOUD][PAYMENT] check failed for {plate_text}: {e}")
            paid = False
            price = 0

        if not paid:
            print(f"[LOGIC] Vehicle {plate_text} has NOT paid (due {price} cents). Denying exit.")
            return

        active = db.get_active_session(plate_text)
        if not active:
            print(
                f"[LOGIC] WARNING: Exit detected for plate {plate_text} "
                "but there is no active 'inside' session in DB. "
                "Possible tailgating or missed entry detection."
            )
            # For now allow exit but log
            await open_barrier(nc_edge, id_)
            return

        print(f"[LOGIC] Plate {plate_text} exiting. Completing session id={active['id']}.")
        db.complete_exit(plate_text)

        # Decrement occupancy and send to cloud
        await tracker.decrement_occupancy()
        print(f"[CLOUD] Updated occupancy to {tracker.current_occupancy}/{tracker.max_capacity}")

        # Inform cloud payment that the car has left to cleanup record
        try:
            del_res = await cloud_client.payment_exit(plate_text)
            print(f"[CLOUD][PAYMENT] exit deleted for {plate_text}: {del_res}")
        except Exception as e:
            print(f"[CLOUD][PAYMENT] exit delete failed for {plate_text}: {e}")

        await open_barrier(nc_edge, id_)

    else:
        print(f"[LOGIC] Unknown checkpoint type for camera id {id_}, raw plate={plate_text}")

def show_image(window_name, img):
    cv2.imshow(window_name, img)
    cv2.waitKey(1)

async def main():
    # Initialize NATS connections
    nc_edge = NATS()
    await nc_edge.connect(EDGE_NATS_URL)
    nc_cloud = NATS()
    await nc_cloud.connect(CLOUD_NATS_URL)

    # Initialize database
    db = ParkingDatabase(DB_PATH, CAR_PARK_ID)
    db.init_db()

    # Initialize cloud client
    cloud_client = CloudParkingClient(CLOUD_URL)

    # Check cloud health
    if await cloud_client.health_check():
        print(f"[CLOUD] Connected to cloud system at {CLOUD_URL}")
    else:
        print(f"[CLOUD] WARNING: Cannot reach cloud system at {CLOUD_URL}")

    # Initialize parking lot tracker
    tracker = ParkingLotTracker(
        cloud_client=cloud_client,
        park_id=CAR_PARK_ID,
        max_capacity=CAR_PARK_CAPACITY,
        lat=CAR_PARK_LAT,
        lng=CAR_PARK_LNG
    )


    # Register parking lot with cloud
    try:
        await tracker.register()
        print(f"[CLOUD] Registered parking lot {CAR_PARK_ID} (capacity: {CAR_PARK_CAPACITY})")
    except Exception as e:
        print(f"[CLOUD] Failed to register parking lot: {e}")

    # Initialize ML models
    model = YOLO(DETECTION_MODEL_PATH, verbose=False)
    reader = easyocr.Reader(["en"], gpu=False)

    async def entry_handler(msg):
        id_ = msg.header.get("camera_id", "unknown")
        jpg = np.frombuffer(msg.data, np.uint8)
        img = cv2.imdecode(jpg, cv2.IMREAD_COLOR)

        print(f"Received entry image from {id_}.")
        # View disabled for now since docker container does not support GUI
        # show_image("Entry Camera", img)

        # YOLO returns a list, but only 1 image - results[0]
        result = model.predict(img, conf=0.25, save=False, verbose=False)[0]

        boxes = result.boxes

        if boxes is None or len(boxes) == 0:
            print("No license plates detected.")
            return

        # ---- Select highest-confidence box ----
        best_box = max(boxes, key=lambda b: float(b.conf[0]))

        xyxy = best_box.xyxy[0].cpu().numpy().astype(int)
        x1, y1, x2, y2 = xyxy
        conf = float(best_box.conf[0])

        # ---- Crop license plate ----
        plate_crop = img[y1:y2, x1:x2]
        # View disabled for now since docker container does not support GUI
        # show_image("Entry Camera Plate Crop", plate_crop)

        # ---- Run OCR ----
        ocr_results = reader.readtext(plate_crop)

        plate_text = None
        if len(ocr_results) > 0:
            # each result = [bbox, text, confidence]
            plate_text = ocr_results[0][1]
            await checkpoint_handler(plate_text, id_, nc_edge, db, tracker, cloud_client)
        else:
            plate_text = "OCR failed to detect text"
        print(f"Detected Plate Box: {x1,y1,x2,y2} (YOLO conf={conf:.2f})")
        print(f"OCR Result: {plate_text}")

    await nc_edge.subscribe("camera.entry", cb=entry_handler)

    async def exit_handler(msg):
        id_ = msg.header.get("camera_id", "unknown")
        jpg = np.frombuffer(msg.data, np.uint8)
        img = cv2.imdecode(jpg, cv2.IMREAD_COLOR)

        print(f"Received exit image from {id_}.")
        # View disabled for now since docker container does not support GUI
        # cv2.imshow("Exit Camera", img)


        # --- YOLO detection (same as entry) ---
        result = model.predict(img, conf=0.25, save=False, verbose=False)[0]
        boxes = result.boxes

        if boxes is None or len(boxes) == 0:
            print("[EXIT] No license plates detected.")
            return

        best_box = max(boxes, key=lambda b: float(b.conf[0]))
        xyxy = best_box.xyxy[0].cpu().numpy().astype(int)
        x1, y1, x2, y2 = xyxy
        conf = float(best_box.conf[0])

        plate_crop = img[y1:y2, x1:x2]
        # show_image("Exit Camera Plate Crop", plate_crop)

        # --- OCR ---
        ocr_results = reader.readtext(plate_crop)
        plate_text = None
        if len(ocr_results) > 0:
            plate_text = ocr_results[0][1]
            await checkpoint_handler(plate_text, id_, nc_edge, db, tracker, cloud_client)
        else:
            plate_text = "OCR failed to detect text"

        print(f"[EXIT] Detected Plate Box: {x1,y1,x2,y2} (YOLO conf={conf:.2f})")
        print(f"[EXIT] OCR Result: {plate_text}")

    await nc_edge.subscribe("camera.exit", cb=exit_handler)

    # Subscribe to booking events for this parking lot via cloud NATS
    async def booking_handler(msg):
        try:
            import json
            data = json.loads(msg.data.decode("utf-8"))
            plate = data.get("licensePlate")
            action = data.get("action")
            if not plate:
                print("[BOOKING] Received booking message without licensePlate")
                return
            if action == "book":
                print(f"[BOOKING] Received booking for {plate} -> increasing occupancy and tracking booking")
                await tracker.add_booking(plate)
            elif action == "cancel":
                print(f"[BOOKING] Received cancel for {plate} -> removing booking and decreasing occupancy if present")
                await tracker.cancel_booking_safe(plate)
            else:
                print(f"[BOOKING] Unknown action '{action}' for plate {plate}")
        except Exception as e:
            print(f"[BOOKING] Failed to process booking message: {e}")

    await nc_cloud.subscribe(f"booking.{CAR_PARK_ID}", cb=booking_handler)

    print("Camera subscriber running...")
    print(f"Parking Lot: {CAR_PARK_ID} (Capacity: {CAR_PARK_CAPACITY})")
    print(f"Cloud URL: {CLOUD_URL}")

    try:
        await asyncio.Future()  # run forever until cancelled
    finally:
        await nc_edge.drain()
        await nc_cloud.drain()
        await cloud_client.close()

asyncio.run(main())
