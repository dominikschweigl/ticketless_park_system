// NO base url needed when using vite proxy
const BASE = "";

export async function getRegisteredParkingLots() {
  const res = await fetch(`${BASE}/api/parking-lots`);
  if (!res.ok) throw new Error("Failed to load parking lots");
  return res.json();
}

export async function getParkingLotStatus(parkId) {
  const res = await fetch(`${BASE}/api/parking-lots/${encodeURIComponent(parkId)}`);
  if (!res.ok) throw new Error(`Failed to load status for ${parkId}`);
  return res.json();
}

export async function createBooking(parkId, licensePlate) {
  const res = await fetch("/api/bookings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parkId, licensePlate }),
  });

  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(txt || "Booking failed");
  }

  // returns JSON: { parkId, licensePlate, status }
  return res.json();
}
