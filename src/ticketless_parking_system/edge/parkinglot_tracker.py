from cloud_parking_client import CloudParkingClient
import logging

logger = logging.getLogger(__name__)

class ParkingLotTracker:
    """
    Tracks parking lot occupancy and sends periodic updates to the cloud.

    This class maintains local state and ensures the cloud system stays in sync.
    """

    def __init__(
        self,
        cloud_client: CloudParkingClient,
        park_id: str,
        max_capacity: int
    ):
        """
        Initialize the parking lot tracker.

        Args:
            cloud_client: Client for communicating with cloud
            park_id: Unique parking lot identifier
            max_capacity: Maximum parking capacity
        """
        self.cloud_client = cloud_client
        self.park_id = park_id
        self.max_capacity = max_capacity
        self.current_occupancy = 0
        self.registered = False

    async def register(self):
        """Register this parking lot with the cloud system."""
        if not self.registered:
            await self.cloud_client.register_parking_lot(
                self.park_id,
                self.max_capacity
            )
            self.registered = True

    async def deregister(self):
        """
        Deregister this parking lot from the cloud system.

        Call this when the edge server is shutting down or
        the parking lot is being permanently closed.
        """
        if self.registered:
            await self.cloud_client.deregister_parking_lot(self.park_id)
            self.registered = False
            logger.info(f"Parking lot {self.park_id} deregistered from cloud")

    async def update_occupancy(self, new_occupancy: int):
        """
        Update occupancy and send to cloud.

        Args:
            new_occupancy: New occupancy count (from sensors)
        """
        if new_occupancy < 0:
            logger.warning(f"Invalid occupancy {new_occupancy}, setting to 0")
            new_occupancy = 0
        elif new_occupancy > self.max_capacity:
            logger.warning(
                f"Occupancy {new_occupancy} exceeds capacity {self.max_capacity}, "
                f"capping at capacity"
            )
            new_occupancy = self.max_capacity

        if new_occupancy != self.current_occupancy:
            logger.info(
                f"Occupancy changed: {self.current_occupancy} -> {new_occupancy}"
            )
            self.current_occupancy = new_occupancy

        await self.cloud_client.send_occupancy_update(
            self.park_id,
            self.current_occupancy
        )

    async def increment_occupancy(self):
        """Increment occupancy by 1 (car entered)."""
        await self.update_occupancy(self.current_occupancy + 1)

    async def decrement_occupancy(self):
        """Decrement occupancy by 1 (car exited)."""
        await self.update_occupancy(self.current_occupancy - 1)

    def get_available_spaces(self) -> int:
        """Get number of available parking spaces."""
        return max(0, self.max_capacity - self.current_occupancy)

    def is_full(self) -> bool:
        """Check if parking lot is full."""
        return self.current_occupancy >= self.max_capacity