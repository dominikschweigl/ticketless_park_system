#!/usr/bin/env python3
"""
Test script for Cloud Parking Client.
Tests the HTTP communication with the Akka cloud system.
"""

import asyncio
import sys
from cloud_parking_client import CloudParkingClient
from parkinglot_tracker import ParkingLotTracker


async def test_basic_client():
    """Test basic client functionality."""
    print("=" * 60)
    print("Testing CloudParkingClient")
    print("=" * 60)

    client = CloudParkingClient("http://localhost:8080")

    try:
        # 1. Health check
        print("\n1. Health Check...")
        healthy = await client.health_check()
        print(f"   ✓ Cloud system healthy: {healthy}")
        if not healthy:
            print("   ✗ Cloud system not reachable!")
            return False

        # 2. Register parking lot
        print("\n2. Register Parking Lot...")
        result = await client.register_parking_lot(
            park_id="test-lot-01",
            max_capacity=100
        )
        print(f"   ✓ Registered: {result}")

        # 3. Send occupancy update
        print("\n3. Send Occupancy Update (25 cars)...")
        result = await client.send_occupancy_update(
            park_id="test-lot-01",
            current_occupancy=25
        )
        print(f"   ✓ Update sent: {result}")

        # 4. Get status
        print("\n4. Query Parking Lot Status...")
        status = await client.get_parking_lot_status("test-lot-01")
        print(f"   ✓ Status:")
        print(f"     - Park ID: {status['parkId']}")
        print(f"     - Current Occupancy: {status['currentOccupancy']}")
        print(f"     - Max Capacity: {status['maxCapacity']}")
        print(f"     - Available Spaces: {status['availableSpaces']}")

        # 5. Update occupancy again
        print("\n5. Send Another Update (30 cars)...")
        result = await client.send_occupancy_update(
            park_id="test-lot-01",
            current_occupancy=30
        )
        print(f"   ✓ Update sent: {result}")

        # 6. Verify new status
        print("\n6. Verify Updated Status...")
        status = await client.get_parking_lot_status("test-lot-01")
        print(f"   ✓ Current Occupancy: {status['currentOccupancy']}")
        print(f"   ✓ Available Spaces: {status['availableSpaces']}")

        # 7. Get all registered parking lots
        print("\n7. Get All Registered Parking Lots...")
        parks = await client.get_registered_parking_lots()
        print(f"   ✓ Registered parks: {parks['parks']}")
        if 'test-lot-01' in parks['parks']:
            print(f"   ✓ test-lot-01 found with capacity {parks['parks']['test-lot-01']}")

        print("\n" + "=" * 60)
        print("✓ All basic client tests passed!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.close()


async def test_parking_lot_tracker():
    """Test ParkingLotTracker functionality."""
    print("\n" + "=" * 60)
    print("Testing ParkingLotTracker")
    print("=" * 60)

    client = CloudParkingClient("http://localhost:8080")

    try:
        # Create tracker
        print("\n1. Create Tracker...")
        tracker = ParkingLotTracker(
            cloud_client=client,
            park_id="test-lot-02",
            max_capacity=50
        )
        print(f"   ✓ Tracker created for lot test-lot-02 (capacity: 50)")

        # Register
        print("\n2. Register Parking Lot...")
        await tracker.register()
        print(f"   ✓ Registered with cloud")

        # Simulate cars entering
        print("\n3. Simulate Cars Entering...")
        for i in range(5):
            await tracker.increment_occupancy()
            print(f"   Car {i+1} entered - Occupancy: {tracker.current_occupancy}/{tracker.max_capacity}")

        # Check available spaces
        print(f"\n4. Available Spaces: {tracker.get_available_spaces()}")
        print(f"   Is Full: {tracker.is_full()}")

        # Simulate cars leaving
        print("\n5. Simulate Cars Leaving...")
        for i in range(3):
            await tracker.decrement_occupancy()
            print(f"   Car {i+1} left - Occupancy: {tracker.current_occupancy}/{tracker.max_capacity}")

        # Verify with cloud
        print("\n6. Verify State with Cloud...")
        status = await client.get_parking_lot_status("test-lot-02")
        print(f"   Cloud Occupancy: {status['currentOccupancy']}")
        print(f"   Local Occupancy: {tracker.current_occupancy}")

        if status['currentOccupancy'] == tracker.current_occupancy:
            print("   ✓ Cloud and local state match!")
        else:
            print("   ✗ State mismatch!")
            return False

        print("\n" + "=" * 60)
        print("✓ All tracker tests passed!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.close()


async def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "Cloud Parking Client Test Suite" + " " * 16 + "║")
    print("╚" + "=" * 58 + "╝")

    print("\nMake sure the Akka cloud system is running on http://localhost:8080")
    print("Press Enter to continue or Ctrl+C to cancel...")
    try:
        input()
    except KeyboardInterrupt:
        print("\nTest cancelled.")
        return

    # Run tests
    test1 = await test_basic_client()
    test2 = await test_parking_lot_tracker()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Basic Client Tests:       {'✓ PASSED' if test1 else '✗ FAILED'}")
    print(f"Parking Lot Tracker Tests: {'✓ PASSED' if test2 else '✗ FAILED'}")
    print("=" * 60)

    if test1 and test2:
        print("\n🎉 All tests passed! Your Python ↔ Akka communication works!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Check the output above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

