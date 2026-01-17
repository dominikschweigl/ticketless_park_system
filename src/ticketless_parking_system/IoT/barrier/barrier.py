import asyncio
import os
import threading
import tkinter as tk
from nats.aio.client import Client as NATS
import json
from datetime import datetime, timezone

NATS_URL = os.environ.get("NATS_URL", "nats://localhost:4222")
BARRIER_ID = os.environ.get("BARRIER_ID", "barrier0")


class BarrierUI:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Barrier Simulator")

        self.canvas = tk.Canvas(self.root, width=300, height=150)
        self.canvas.pack(padx=10, pady=10)

        # barrier
        self.barrier_rect = self.canvas.create_rectangle(
            50, 60, 250, 90, fill="red"
        )

        self.status_var = tk.StringVar(value="Closed")
        self.status_label = tk.Label(self.root, textvariable=self.status_var, font=("Arial", 14))
        self.status_label.pack(pady=5)

    def _set_barrier_state_sync(self, state: str):
        
        if state == "open":
            self.canvas.itemconfig(self.barrier_rect, fill="green")
            self.status_var.set("Open")
        else:
            self.canvas.itemconfig(self.barrier_rect, fill="red")
            self.status_var.set("Closed")

    def set_barrier_state(self, state: str):   #thread-safe
        
        self.root.after(0, self._set_barrier_state_sync, state)



class BarrierSensorController:
    """
    simulates two sensors:
    - detect_vehicle: light sensor before the barrier
    - vehicle_passed: sensor behind the barrier
    """

    def __init__(self):
        #hardware initialization, boilerplate, etc.
        pass

    async def detect_vehicle(self) -> bool:
        # TODO: sensor simulation / real sensor logic here
        await asyncio.sleep(0.5)
        detected = True  # GPIO function call       
        return detected                 

    async def vehicle_passed(self) -> bool:
        # TODO: sensor simulation / real sensor logic here
        await asyncio.sleep(0.5)
        passed = True  # GPIO function call
        return passed           


class BarrierController:
    def __init__(self, sensor: BarrierSensorController, ui: BarrierUI = None, nc: NATS = None, barrier_id: str = BARRIER_ID):
        self.sensor = sensor
        self.ui = ui
        self.nc = nc
        self.barrier_id = barrier_id
        self._lock = asyncio.Lock()  

    async def _publish_state(self, state: str, ok: bool = True, info: str = ""):
        if not self.nc:
            return
        payload = {
            "barrier_id": self.barrier_id,
            "state": state,
            "ok": ok,
            "info": info,
            "ts": datetime.now(timezone.utc).isoformat()
        }
        await self.nc.publish(f"{self.barrier_id}.state", json.dumps(payload).encode("utf-8"))

    async def open_barrier(self) -> bool:
        async with self._lock:
            try:
                await self._publish_state("checking")
                detected = await asyncio.wait_for(self.sensor.detect_vehicle(), timeout=10)
                if not detected:
                    await self._publish_state("closed", ok=False, info="no_vehicle_detected")
                    return False

                if self.ui:
                    self.ui.set_barrier_state("open")
                await self._publish_state("opening")
                await asyncio.sleep(0.5)

                try:
                    passed = await asyncio.wait_for(self.sensor.vehicle_passed(), timeout=10)
                    if not passed:
                        await self._publish_state("closing", ok=False, info="vehicle_not_passed")
                        await self.close_barrier()
                        return False

                    await asyncio.sleep(0.5)
                    await self._publish_state("closing")
                    await self.close_barrier()
                    await self._publish_state("closed")
                    return True

                except asyncio.TimeoutError:
                    await self._publish_state("closing", ok=False, info="timeout_vehicle_passed")
                    await self.close_barrier()
                    await self._publish_state("closed", ok=False)
                    return False

            except asyncio.TimeoutError:
                await self._publish_state("closed", ok=False, info="timeout_detect_vehicle")
                await self.close_barrier()
                return False

    async def close_barrier(self):
        if self.ui:
            self.ui.set_barrier_state("closed")
        await asyncio.sleep(0.5)


async def main(ui):
    nc = NATS()
    await nc.connect(NATS_URL)

    sensor = BarrierSensorController()
    barrier_component = BarrierController(sensor, ui = ui, nc=nc, barrier_id=BARRIER_ID)

    async def barrier_callback(msg):
        print("Received barrier trigger:", msg.subject)
        success = await barrier_component.open_barrier()
        rep_payload = b"done" if success else b"failed"

      
        if msg.reply:
            await nc.publish(msg.reply, rep_payload)

   
    await nc.subscribe(f"{BARRIER_ID}.trigger", cb=barrier_callback)

    

    try:
       
        await asyncio.Future()  
    finally:
        await nc.drain()

def start_loop(ui):
    asyncio.run(main(ui))
if __name__ == "__main__":
    #ui = BarrierUI() -- deactivate for docker --
    #t = threading.Thread(target=start_loop, args=(None,)) # deactivate for docker --
    #t.start()
    asyncio.run(main(None)) 
    #ui.root.mainloop()