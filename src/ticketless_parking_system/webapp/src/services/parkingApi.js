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
