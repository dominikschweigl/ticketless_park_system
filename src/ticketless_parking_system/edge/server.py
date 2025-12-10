import os
import cv2
import numpy as np
import asyncio
from nats.aio.client import Client as NATS
from ultralytics import YOLO
import easyocr

NATS_URL = os.environ.get("NATS_URL")
DETECTION_MODEL_PATH = os.environ.get("DETECTION_MODEL_PATH")

def show_image(window_name, img):
    cv2.imshow(window_name, img)
    cv2.waitKey(1)

async def main():
    nc = NATS()
    await nc.connect(NATS_URL)

    model = YOLO(DETECTION_MODEL_PATH, verbose=False)
    reader = easyocr.Reader(["en"], gpu=False)

    async def entry_handler(msg):
        jpg = np.frombuffer(msg.data, np.uint8)
        img = cv2.imdecode(jpg, cv2.IMREAD_COLOR)
        
        print("Received entry image.")
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
        else:
            plate_text = "OCR failed to detect text"

        print(f"Detected Plate Box: {x1,y1,x2,y2} (YOLO conf={conf:.2f})")
        print(f"OCR Result: {plate_text}")
        
    await nc.subscribe("camera.entry", cb=entry_handler)

    async def exit_handler(msg):
        jpg = np.frombuffer(msg.data, np.uint8)
        img = cv2.imdecode(jpg, cv2.IMREAD_COLOR)

        print("Received exit image.")
        # View disabled for now since docker container does not support GUI
        # cv2.imshow("Exit Camera", img)
        
    await nc.subscribe("camera.exit", cb=exit_handler)

    print("Camera subscriber running...")
    while True:
        if cv2.pollKey() == 27:  # ESC key
            break
        await asyncio.sleep(1)

asyncio.run(main())
