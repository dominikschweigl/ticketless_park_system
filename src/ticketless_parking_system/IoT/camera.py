import cv2
import zmq
import time

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://*:5555")

frame = cv2.imread("./data/Cars0.png")

if frame is None:
    raise ValueError("Could not load image.")

while True:
    _, buf = cv2.imencode('.jpg', frame)
    socket.send(buf)
    time.sleep(0.03)