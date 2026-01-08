"""
Client for communicating with the Akka Cloud Parking System.
Provides simple Python interface to register parking lots and send occupancy updates.
"""

import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class CloudParkingClient:
    """
    HTTP client for communicating with the Akka-based cloud parking system.

    The cloud system provides:
    - Parking lot registration
    - Occupancy updates
    - Parking lot status queries
    """

    def __init__(self, base_url: str, timeout: float = 5.0):
        """
        Initialize the cloud client.

        Args:
            base_url: Base URL of the cloud system (e.g., "http://localhost:8080")
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def health_check(self) -> bool:
        """
        Check if the cloud system is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def register_parking_lot(
        self,
        park_id: str,
        max_capacity: int,
        lat: float,
        lng: float
    ) -> Dict[str, Any]:
        """
        Register a new parking lot with the cloud system.

        Args:
            park_id: Unique identifier for the parking lot
            max_capacity: Maximum number of cars that can park

        Returns:
            Response dict with registration confirmation

        Raises:
            httpx.HTTPStatusError: If registration fails
        """
        url = f"{self.base_url}/api/parking-lots"
        data = {
            "parkId": park_id,
            "maxCapacity": max_capacity,
            "lat": lat, 
            "lng": lng
        }

        logger.info(f"Registering parking lot {park_id} (capacity: {max_capacity})")

        response = await self.client.post(url, json=data)
        response.raise_for_status()

        result = response.json()
        logger.info(f"Parking lot {park_id} registered successfully: {result}")
        return result

    async def send_occupancy_update(
        self,
        park_id: str,
        current_occupancy: int
    ) -> Dict[str, Any]:
        """
        Send current occupancy update to the cloud system.

        This is the PRIMARY way to communicate parking lot state.
        Send this periodically (e.g., every 30 seconds) or when occupancy changes.

        Args:
            park_id: Identifier of the parking lot
            current_occupancy: Current number of cars in the lot

        Returns:
            Response dict with acceptance confirmation

        Raises:
            httpx.HTTPStatusError: If update fails
        """
        url = f"{self.base_url}/api/occupancy"
        data = {
            "parkId": park_id,
            "currentOccupancy": current_occupancy
        }

        logger.debug(f"Sending occupancy update for {park_id}: {current_occupancy} cars")

        response = await self.client.post(url, json=data)
        response.raise_for_status()

        return response.json()

    async def get_parking_lot_status(self, park_id: str) -> Dict[str, Any]:
        """
        Query the current status of a parking lot.

        Args:
            park_id: Identifier of the parking lot

        Returns:
            Dict with:
                - parkId: The parking lot ID
                - currentOccupancy: Number of cars currently parked
                - maxCapacity: Maximum capacity
                - availableSpaces: Number of available spaces

        Raises:
            httpx.HTTPStatusError: If query fails (e.g., lot not found)
        """
        url = f"{self.base_url}/api/parking-lots/{park_id}"

        response = await self.client.get(url)
        response.raise_for_status()

        return response.json()

    async def get_registered_parking_lots(self) -> Dict[str, Any]:
        """
        Get all registered parking lots from the cloud system.

        Returns:
            Dict with:
                - parks: Dictionary mapping parkId (str) to maxCapacity (int)
                  Example: {"lot-01": 50, "lot-02": 100, "lot-03": 25}

        Raises:
            httpx.HTTPStatusError: If query fails
        """
        url = f"{self.base_url}/api/parking-lots"

        response = await self.client.get(url)
        response.raise_for_status()

        return response.json()

    async def deregister_parking_lot(self, park_id: str) -> Dict[str, Any]:
        """
        Deregister a parking lot from the cloud system.

        This should be called when an edge server goes offline or
        a parking lot is permanently closed.

        Args:
            park_id: Unique identifier for the parking lot to deregister

        Returns:
            Response dict with deregistration confirmation
            Example: {"parkId": "lot-01", "status": "deregistered"}

        Raises:
            httpx.HTTPStatusError: If deregistration fails (e.g., lot not found)
        """
        url = f"{self.base_url}/api/parking-lots/{park_id}"

        logger.info(f"Deregistering parking lot {park_id}")

        response = await self.client.delete(url)
        response.raise_for_status()

        result = response.json()
        logger.info(f"Parking lot {park_id} deregistered successfully: {result}")
        return result

    async def payment_car_enter(self, license_plate: str, entry_timestamp: int | None = None) -> Dict[str, Any]:
        """
        Notify the cloud that a car has entered (record entry timestamp).

        Args:
            license_plate: Car license plate identifier
            entry_timestamp: Optional epoch millis; if None, server will use current time

        Returns:
            Dict with status information, e.g., {"status": "recorded"}
        """
        url = f"{self.base_url}/api/payment/enter"
        data = {"licensePlate": license_plate}
        if entry_timestamp is not None:
            data["entryTimestamp"] = entry_timestamp

        resp = await self.client.post(url, json=data)
        # Expected 202 Accepted with plain text body "recorded"
        if resp.status_code not in (200, 202):
            resp.raise_for_status()
        txt = resp.text.strip()
        # Normalize into dict
        return {"status": txt or "recorded"}

    async def payment_pay(self, license_plate: str) -> Dict[str, Any]:
        """
        Mark a car as paid and return computed price based on parking duration.

        Returns the PaymentStatus JSON from the server.
        """
        url = f"{self.base_url}/api/payment/pay"
        data = {"licensePlate": license_plate}
        resp = await self.client.post(url, json=data)
        resp.raise_for_status()
        return resp.json()

    async def payment_check(self, license_plate: str) -> Dict[str, Any]:
        """
        Check payment status when the car is leaving the car park.

        Returns the PaymentStatus JSON from the server.
        """
        url = f"{self.base_url}/api/payment/check"
        resp = await self.client.get(url, params={"licensePlate": license_plate})
        resp.raise_for_status()
        return resp.json()

    async def payment_exit(self, license_plate: str) -> Dict[str, Any]:
        """
        Delete the car's session after it left the car park.

        Returns dict {"status": "deleted"} on success.
        """
        url = f"{self.base_url}/api/payment/exit"
        resp = await self.client.delete(url, params={"licensePlate": license_plate})
        if resp.status_code not in (200, 202):
            resp.raise_for_status()
        txt = resp.text.strip()
        return {"status": txt or "deleted"}
