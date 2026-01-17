import os
import json
import asyncio
from typing import Optional

import cv2
import numpy as np
from nats.aio.client import Client as NATS
from nats import errors as nats_errors
from nats.errors import TimeoutError as NATSTimeoutError

from ultralytics import YOLO
import easyocr

from edge_db import ParkingDatabase

# Optional cloud modules (werden nur genutzt wenn CLOUD_ENABLED=1)
try:
    from cloud_parking_client import CloudParkingClient
    from parkinglot_tracker import ParkingLotTracker
except Exception:
    CloudParkingClient = None
    ParkingLotTracker = None


# -----------------------------
# Config
# -----------------------------
DETECTION_MODEL_PATH = os.environ.get("DETECTION_MODEL_PATH", "")
DB_PATH = os.environ.get("DB_PATH", "parking.db")
CAR_PARK_ID = os.environ.get("CAR_PARK_ID", "lot-01")
CAR_PARK_CAPACITY = int(os.environ.get("CAR_PARK_CAPACITY", "67"))

EDGE_NATS_URL = os.environ.get("EDGE_NATS_URL", "nats://nats:4222")

CLOUD_ENABLED = os.environ.get("CLOUD_ENABLED", "1") == "1"
CLOUD_URL = os.environ.get("CLOUD_URL", "http://parking-system-cloud:8080")
CLOUD_NATS_URL = os.environ.get("CLOUD_NATS_URL", "nats://parking-system-cloud-nats:4222")

# Exit policy in edge-only mode:
# - if 1: allow exits without cloud payment check (good for demo)
# - if 0: deny exits without cloud payment check
ALLOW_EXIT_WITHOUT_CLOUD = os.environ.get("ALLOW_EXIT_WITHOUT_CLOUD", "1") == "1"

# OCR / detection tuning
YOLO_CONF = float(os.environ.get("YOLO_CONF", "0.25"))

# Barrier request timeout
BARRIER_TIMEOUT_S = float(os.environ.get("BARRIER_TIMEOUT_S", "10"))


# -----------------------------
# Helpers
# -----------------------------
def parse_checkpoint(camera_id: str) -> tuple[str, str]:
    """
    Expected camera_id like: "entry_0" or "exit_0"
    returns (checkpoint_type, barrier_id)
      - checkpoint_type = "entry" or "exit"
      - barrier_id = same as camera_id ("entry_0" / "exit_0")
    """
    parts = (camera_id or "").split("_", 1)
    if len(parts) != 2:
        return ("unknown", camera_id or "unknown")
    checkpoint_type = parts[0].lower().strip()
    return (checkpoint_type, camera_id)


def pick_best_plate(boxes) -> Optional[object]:
    if boxes is None or len(boxes) == 0:
        return None
    return max(boxes, key=lambda b: float(b.conf[0]))


def ocr_plate(reader: easyocr.Reader, plate_crop: np.ndarray) -> Optional[str]:
    try:
        results = reader.readtext(plate_crop)
        if not results:
            return None
        # pick best by confidence if available
        best = max(results, key=lambda r: float(r[2]) if len(r) >= 3 else 0.0)
        text = best[1].strip()
        return text if text else None
    except Exception:
        return None


async def open_barrier(nc_edge: NATS, barrier_id: str) -> bool:
    subject = f"{barrier_id}.trigger"
    try:
        reply = await nc_edge.request(subject, b"", timeout=BARRIER_TIMEOUT_S)
        if reply.data == b"done":
            print(f"[BARRIER] OK: {subject} -> done")
            return True
        print(f"[BARRIER] WARN: {subject} -> {reply.data!r}")
        return False

    except nats_errors.NoRespondersError:
        # Demo-friendly: barrier service not running -> simulate success
        print(f"[BARRIER][SIM] No responders on {subject}. Simulating open.")
        return True

    except NATSTimeoutError:
        print(f"[BARRIER] TIMEOUT waiting for reply on {subject}")
        return False

    except Exception as e:
        print(f"[BARRIER] ERROR calling {subject}: {e}")
        return False


# -----------------------------
# Main logic
# -----------------------------
async def handle_checkpoint(
    checkpoint_type: str,
    barrier_id: str,
    plate_text: str,
    nc_edge: NATS,
    db: ParkingDatabase,
    tracker,
    cloud_client,
):
    plate_text = plate_text.strip()
    if not plate_text:
        print("[LOGIC] Empty plate_text -> ignore")
        return

    if checkpoint_type == "entry":
        active = db.get_active_session(plate_text)
        if active:
            print(f"[LOGIC][ENTRY] {plate_text} already inside since {active['entry_time']}, opening anyway.")
            await open_barrier(nc_edge, barrier_id)
            return

        print(f"[LOGIC][ENTRY] {plate_text} entering -> create session")
        db.register_entry(plate_text)

        # cloud optional
        if cloud_client and tracker:
            try:
                pay_res = await cloud_client.payment_car_enter(plate_text)
                print(f"[CLOUD][PAYMENT] enter recorded for {plate_text}: {pay_res}")
            except Exception as e:
                print(f"[CLOUD][PAYMENT] enter failed for {plate_text}: {e}")

            try:
                if tracker.has_booking(plate_text):
                    print(f"[BOOKING] Consume booking for {plate_text}")
                    tracker.consume_booking(plate_text)
                else:
                    await tracker.increment_occupancy()
                    print(f"[CLOUD] occupancy={tracker.current_occupancy}/{tracker.max_capacity}")
            except Exception as e:
                print(f"[CLOUD] occupancy update failed: {e}")
        else:
            print("[CLOUD] disabled: skipping payment/occupancy for ENTRY")

        await open_barrier(nc_edge, barrier_id)

    elif checkpoint_type == "exit":
        # in edge-only mode: either allow or deny
        if not (cloud_client and tracker):
            if not ALLOW_EXIT_WITHOUT_CLOUD:
                print(f"[LOGIC][EXIT] {plate_text} exit denied (cloud disabled)")
                return
            print(f"[LOGIC][EXIT] {plate_text} cloud disabled -> allowing exit for demo")
        else:
            # cloud payment check
            paid = False
            price = 0
            try:
                status = await cloud_client.payment_check(plate_text)
                paid = bool(status.get("paid", False))
                price = status.get("priceCents", 0)
                print(f"[CLOUD][PAYMENT] check {plate_text}: paid={paid}, priceCents={price}")
            except Exception as e:
                print(f"[CLOUD][PAYMENT] check failed for {plate_text}: {e}")

            if not paid:
                print(f"[LOGIC][EXIT] {plate_text} NOT paid (due {price} cents) -> deny exit")
                return

        active = db.get_active_session(plate_text)
        if not active:
            print(f"[LOGIC][EXIT] WARNING: {plate_text} exit but no active session -> still opening (demo)")
            await open_barrier(nc_edge, barrier_id)
            return

        print(f"[LOGIC][EXIT] {plate_text} exiting -> complete session id={active['id']}")
        db.complete_exit(plate_text)

        if cloud_client and tracker:
            try:
                await tracker.decrement_occupancy()
                print(f"[CLOUD] occupancy={tracker.current_occupancy}/{tracker.max_capacity}")
            except Exception as e:
                print(f"[CLOUD] occupancy decrement failed: {e}")

            try:
                del_res = await cloud_client.payment_exit(plate_text)
                print(f"[CLOUD][PAYMENT] exit deleted for {plate_text}: {del_res}")
            except Exception as e:
                print(f"[CLOUD][PAYMENT] exit delete failed for {plate_text}: {e}")
        else:
            print("[CLOUD] disabled: skipping payment/occupancy for EXIT")

        await open_barrier(nc_edge, barrier_id)

    else:
        print(f"[LOGIC] Unknown checkpoint_type='{checkpoint_type}' (camera_id='{barrier_id}') plate='{plate_text}'")


# -----------------------------
# Entry/Exit NATS handlers
# -----------------------------
async def main():
    print(f"[EDGE] starting with EDGE_NATS_URL={EDGE_NATS_URL}")
    print(f"[EDGE] CLOUD_ENABLED={CLOUD_ENABLED} ALLOW_EXIT_WITHOUT_CLOUD={ALLOW_EXIT_WITHOUT_CLOUD}")

    if not DETECTION_MODEL_PATH:
        raise RuntimeError("DETECTION_MODEL_PATH is not set (YOLO model path).")

    # NATS edge
    nc_edge = NATS()
    await nc_edge.connect(EDGE_NATS_URL)
    print("[EDGE] connected to NATS (edge)")

    # DB
    db = ParkingDatabase(DB_PATH, CAR_PARK_ID)
    db.init_db()
    print(f"[EDGE] DB ready at {DB_PATH} for park_id={CAR_PARK_ID}")

    # Cloud optional
    nc_cloud = None
    cloud_client = None
    tracker = None

    if CLOUD_ENABLED:
        if CloudParkingClient is None or ParkingLotTracker is None:
            print("[CLOUD] modules not importable -> forcing CLOUD_ENABLED=0")
        else:
            try:
                nc_cloud = NATS()
                await nc_cloud.connect(CLOUD_NATS_URL)
                print(f"[CLOUD] connected to cloud NATS: {CLOUD_NATS_URL}")
            except Exception as e:
                print(f"[CLOUD] FAILED to connect cloud NATS ({CLOUD_NATS_URL}): {e}")
                nc_cloud = None

            try:
                cloud_client = CloudParkingClient(CLOUD_URL)
                ok = await cloud_client.health_check()
                print(f"[CLOUD] health_check {CLOUD_URL} -> {ok}")
            except Exception as e:
                print(f"[CLOUD] health_check failed ({CLOUD_URL}): {e}")
                cloud_client = None

            try:
                if cloud_client:
                    tracker = ParkingLotTracker(
                        cloud_client=cloud_client,
                        park_id=CAR_PARK_ID,
                        max_capacity=CAR_PARK_CAPACITY,
                        lat=float(os.environ.get("CAR_PARK_LAT", "0")),
                        lng=float(os.environ.get("CAR_PARK_LNG", "0")),
                    )
                    await tracker.register()
                    print(f"[CLOUD] registered parking lot {CAR_PARK_ID} capacity={CAR_PARK_CAPACITY}")
            except Exception as e:
                print(f"[CLOUD] tracker/register failed: {e}")
                tracker = None
    else:
        print("[CLOUD] disabled: edge-only mode")

    # ML models
    model = YOLO(DETECTION_MODEL_PATH, verbose=False)
    reader = easyocr.Reader(["en"], gpu=False)
    print("[EDGE] YOLO + OCR initialized")

    async def handle_camera_msg(msg, topic: str):
        # get camera id from header if present
        cam_id = None
        try:
            if msg.headers:
                cam_id = msg.headers.get("camera_id")
        except Exception:
            cam_id = None

        if not cam_id:
            # fallback from subject: camera.entry -> entry (not ideal)
            cam_id = topic

        checkpoint_type, barrier_id = parse_checkpoint(cam_id)

        jpg = np.frombuffer(msg.data, np.uint8)
        img = cv2.imdecode(jpg, cv2.IMREAD_COLOR)
        if img is None:
            print(f"[EDGE] failed to decode jpg from {cam_id}")
            return

        print(f"[EDGE] received {checkpoint_type} frame from camera_id={cam_id} subject={msg.subject}")

        # YOLO
        try:
            result = model.predict(img, conf=YOLO_CONF, save=False, verbose=False)[0]
            boxes = result.boxes
        except Exception as e:
            print(f"[EDGE] YOLO predict failed: {e}")
            return

        best_box = pick_best_plate(boxes)
        if best_box is None:
            print(f"[EDGE] no plate detected ({cam_id})")
            return

        xyxy = best_box.xyxy[0].cpu().numpy().astype(int)
        x1, y1, x2, y2 = xyxy.tolist()
        conf = float(best_box.conf[0])
        # clamp
        h, w = img.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            print("[EDGE] invalid crop after clamp")
            return

        plate_crop = img[y1:y2, x1:x2]

        plate_text = ocr_plate(reader, plate_crop)
        if not plate_text:
            print(f"[EDGE] OCR failed ({cam_id}) yolo_conf={conf:.2f} box={x1,y1,x2,y2}")
            return

        print(f"[EDGE] plate={plate_text} yolo_conf={conf:.2f} box={x1,y1,x2,y2}")
        await handle_checkpoint(checkpoint_type, barrier_id, plate_text, nc_edge, db, tracker, cloud_client)

    async def entry_handler(msg):
        await handle_camera_msg(msg, "entry")

    async def exit_handler(msg):
        await handle_camera_msg(msg, "exit")

    await nc_edge.subscribe("camera.entry", cb=entry_handler)
    await nc_edge.subscribe("camera.exit", cb=exit_handler)
    print("[EDGE] subscribed to camera.entry and camera.exit")

    # optional booking subscribe
    if nc_cloud and tracker:
        async def booking_handler(msg):
            try:
                data = json.loads(msg.data.decode("utf-8"))
                plate = data.get("licensePlate")
                action = data.get("action")
                if not plate:
                    print("[BOOKING] missing licensePlate")
                    return
                if action == "book":
                    print(f"[BOOKING] book {plate}")
                    await tracker.add_booking(plate)
                elif action == "cancel":
                    print(f"[BOOKING] cancel {plate}")
                    await tracker.cancel_booking_safe(plate)
                else:
                    print(f"[BOOKING] unknown action={action} plate={plate}")
            except Exception as e:
                print(f"[BOOKING] parse failed: {e}")

        await nc_cloud.subscribe(f"booking.{CAR_PARK_ID}", cb=booking_handler)
        print(f"[CLOUD] subscribed to booking.{CAR_PARK_ID}")

    try:
        await asyncio.Future()  # run forever
    finally:
        print("[EDGE] shutting down...")
        try:
            await nc_edge.drain()
        except Exception:
            pass
        if nc_cloud:
            try:
                await nc_cloud.drain()
            except Exception:
                pass
        if cloud_client:
            try:
                await cloud_client.close()
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(main())
