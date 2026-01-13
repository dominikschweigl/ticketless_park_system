const API_BASE_URL = window.APP_CONFIG?.API_BASE_URL || "";

export async function getRegisteredParkingLots() {
  const res = await fetch(`${API_BASE_URL}/api/parking-lots`);
  if (!res.ok) throw new Error("Failed to load parking lots");
  return res.json();
}

export async function getParkingLotStatus(parkId) {
  const res = await fetch(`${API_BASE_URL}/api/parking-lots/${encodeURIComponent(parkId)}`);
  if (!res.ok) throw new Error(`Failed to load status for ${parkId}`);
  return res.json();
}

export async function createBooking(parkId, licensePlate) {
  const res = await fetch(`${API_BASE_URL}/api/bookings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parkId, licensePlate }),
  });

  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(txt || "Booking failed");
  }

  return res.json();
}

export async function paymentCheck(licensePlate) {
  const res = await fetch(`${API_BASE_URL}/api/payment/check?licensePlate=${encodeURIComponent(licensePlate)}`);
  if (!res.ok) throw new Error("Failed to check payment");
  return res.json(); // PaymentStatus
}

export async function paymentPay(licensePlate) {
  const res = await fetch(`${API_BASE_URL}/api/payment/pay`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ licensePlate }),
  });
  if (!res.ok) throw new Error("Payment failed");
  return res.json(); // PaymentStatus (paid=true)
}

export async function paymentExit(licensePlate) {
  const res = await fetch(`${API_BASE_URL}/api/payment/exit?licensePlate=${encodeURIComponent(licensePlate)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Exit cleanup failed");
  return res.text(); // "deleted"
}

