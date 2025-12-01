import os
from nats.aio.client import Client as NATS
NATS_URL = os.environ.get("NATS_URL")


class BarrierSensorController:

    __init__(self):
        async def detect_vehicle(self):
            # Simulate vehicle detection logic
            #sensor1
            await asyncio.sleep(1)
            return True
        async def vehicle_passed(self):
            # Simulate vehicle passed logic
            #sensor2
            await asyncio.sleep(1)
            return True

class BarrierController:
    
    __init__(self, BarrierSensorController):
        self.sensor = BarrierSensorController()
    
    async def open_barrier(self):
        try: 
            if asyncio.wait_for(self.sensor.detect_vehicle(), timeout=10):
                print("Open barrier.....") # simulate opening barrier
                try:
                    if asyncio.wait_for(self.sensor.vehicle_passed(), timeout=10):
                        await asyncio.sleep(2)  # simulate time for vehicle to pass
                        print("Closing barrier.....") # simulate closing barrier
                except asyncio.TimeoutError:
                    print("Close barrier anyway: vehicle did not pass in time.") #simulate closing barrier
        except asyncio.TimeoutError:
            print("Error: detecting vehicle.")






def main():
    nc = NATS()
    await nc.connect(NATS_URL)

    sensor = BarrierSensorController()
    barrierComponent = BarrierController(sensor)
    async def barrier_callback(msg):
        if msg.subject == "barrier.trigger":
            success = await barrierComponent.open_barrier()
            repPayload = b"done" if success else b"failed"
            await nc.publish(msg.reply, repPayload)

    await nc.subscribe("barrier.trigger", "barrier", cb=barrier_callback)

    while True:
        await asyncio.sleep(3600) 


if __name__ == "__main__":
    asyncio.run(main())