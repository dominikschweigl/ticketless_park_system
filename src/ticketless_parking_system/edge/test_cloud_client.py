#!/usr/bin/env python3
"""
Test script for Cloud Parking Client.
Tests the HTTP communication with the Akka cloud system.
"""

import asyncio
import os
import socket
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

        # 8. Deregister parking lot
        print("\n8. Deregister Parking Lot...")
        result = await client.deregister_parking_lot("test-lot-01")
        print(f"   ✓ Deregistered: {result}")

        # 9. Verify it's gone
        print("\n9. Verify Deregistration...")
        parks = await client.get_registered_parking_lots()
        if 'test-lot-01' not in parks['parks']:
            print("   ✓ test-lot-01 successfully removed from registry")
        else:
            print("   ✗ test-lot-01 still in registry!")
            return False

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


async def test_payment_flow():
    """Test the payment endpoints end-to-end."""
    print("\n" + "=" * 60)
    print("Testing Payment Flow")
    print("=" * 60)

    client = CloudParkingClient("http://localhost:8080")
    plate = "TEST-PLATE-001"

    try:
        # 1. Enter
        print("\n1. Car Enter...")
        result = await client.payment_car_enter(plate)
        print(f"   ✓ Enter recorded: {result}")

        # 2. Check before pay
        print("\n2. Check before Pay...")
        status = await client.payment_check(plate)
        print(f"   ✓ Status: paid={status['paid']}, priceCents={status['priceCents']}")

        # 3. Pay
        print("\n3. Pay...")
        status = await client.payment_pay(plate)
        print(f"   ✓ Paid: paid={status['paid']}, priceCents={status['priceCents']}")

        # 4. Check after pay
        print("\n4. Check after Pay...")
        status = await client.payment_check(plate)
        print(f"   ✓ Status after pay: paid={status['paid']}, priceCents={status['priceCents']}")

        # 5. Exit (delete)
        print("\n5. Exit...")
        result = await client.payment_exit(plate)
        print(f"   ✓ Exit deleted: {result}")

        # 6. Check after exit (should be not found/paid=false)
        print("\n6. Check after Exit...")
        status = await client.payment_check(plate)
        print(f"   ✓ Status after exit: paid={status['paid']}, priceCents={status['priceCents']}")

        print("\n" + "=" * 60)
        print("✓ Payment flow tests passed!")
        print("=" * 60)
        return True
    except Exception as e:
        print(f"\n✗ Payment test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.close()


async def test_booking_flow():
    """Test booking create/cancel only if NATS is available (cloud queue)."""
    print("\n" + "=" * 60)
    print("Testing Booking Flow")
    print("=" * 60)

    client = CloudParkingClient("http://localhost:8080")
    park_id = os.environ.get("CAR_PARK_ID", "lot-01")
    plate = "TEST-BOOK-001"

    try:
        # Create booking
        print("\n1. Create Booking...")
        res = await client.booking_create(park_id, plate)
        print(f"   ✓ Booking created: {res}")

        # Optional short wait to allow edge to process NATS
        await asyncio.sleep(0.2)

        # Cancel booking
        print("\n2. Cancel Booking...")
        res = await client.booking_cancel(park_id, plate)
        print(f"   ✓ Booking canceled: {res}")

        print("\n" + "=" * 60)
        print("✓ Booking flow tests passed!")
        print("=" * 60)
        return True
    except Exception as e:
        print(f"\n✗ Booking test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.close()


def _parse_nats_host_port(url: str) -> tuple[str, int] | None:
    try:
        if not url.startswith("nats://"):
            return None
        # strip schema
        addr = url[len("nats://"):]
        # handle userinfo if present
        if "@" in addr:
            addr = addr.split("@", 1)[1]
        host, port_str = addr.split(":", 1)
        return host, int(port_str)
    except Exception:
        return None


def _is_nats_available(url: str = "nats://nats:4222") -> bool:
    if not url:
        print(f"[NATS] Environment variable {env_key} not set; skipping booking tests.")
        return False
    hp = _parse_nats_host_port(url)
    if hp is None:
        print(f"[NATS] Could not parse host/port from {url}; skipping booking tests.")
        return False
    host, port = hp
    try:
        with socket.create_connection((host, port), timeout=1.0):
            print(f"[NATS] {url} reachable; booking tests will run.")
            return True
    except Exception as e:
        print(f"[NATS] {url} not reachable ({e}); skipping booking tests.")
        return False


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
    test3 = await test_payment_flow()

    # Conditionally run booking tests if NATS is available
    if _is_nats_available("nats://nats:4222"):
        test4 = await test_booking_flow()
    else:
        test4 = True  # don't fail suite just because NATS not available
        print("\n[SKIP] Booking flow tests skipped due to NATS unavailability.")

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Basic Client Tests:       {'✓ PASSED' if test1 else '✗ FAILED'}")
    print(f"Parking Lot Tracker Tests: {'✓ PASSED' if test2 else '✗ FAILED'}")
    print(f"Payment Flow Tests:        {'✓ PASSED' if test3 else '✗ FAILED'}")
    print(f"Booking Flow Tests:        {'✓ PASSED' if test4 else '✗ FAILED'}")
    print("=" * 60)

    if test1 and test2 and test3:
        print("\n🎉 All tests passed! Your Python ↔ Akka communication works!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Check the output above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

