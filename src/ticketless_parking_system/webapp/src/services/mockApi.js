/**
 * MOCK API SERVICE
 * Simulates calls to the Cloud/Akka Actors described in the PDF.
 * This separates the data logic from the UI logic.
 */
export const mockApi = {
  // Simulate fetching parking lots with live capacity (Edge server -> Cloud updates)
  getParkingLots: async () => {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve([
          { id: 1, name: "Central Station Plaza", address: "12 Station Rd", total: 150, free: 12, price: 4.5, dist: "0.4 km" },
          { id: 2, name: "Downtown Market", address: "88 Main St", total: 80, free: 0, price: 5.0, dist: "1.2 km" },
          { id: 3, name: "Westside Garage", address: "420 West Ave", total: 200, free: 145, price: 3.0, dist: "2.5 km" },
          { id: 4, name: "Harbor View", address: "1 Dockside Ln", total: 60, free: 5, price: 6.5, dist: "3.1 km" },
        ]);
      }, 800);
    });
  },

  // Simulate checking payment status for a license plate
  checkPaymentStatus: async (plate) => {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        // Mock logic: Plates ending in 'X' have unpaid fees
        if (plate.toUpperCase().endsWith('X')) {
          resolve({ status: 'UNPAID', amount: 12.50, duration: '2h 15m', entryTime: '10:30 AM' });
        } else if (plate.length < 3) {
            reject({ message: "Invalid license plate format" });
        } else {
          resolve({ status: 'PAID', amount: 0 });
        }
      }, 1200);
    });
  },

  // Simulate processing a payment
  processPayment: async (plate, amount) => {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({ success: true, transactionId: "TXN-" + Math.floor(Math.random() * 100000) });
      }, 1500);
    });
  },

  // Simulate booking a spot
  bookSpot: async (lotId, plate, time) => {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({ success: true, bookingRef: "BK-" + Math.floor(Math.random() * 9999) });
      }, 1000);
    });
  }
};