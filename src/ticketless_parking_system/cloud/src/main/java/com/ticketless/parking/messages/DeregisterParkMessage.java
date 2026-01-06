package com.ticketless.parking.messages;

/**
 * Message to deregister a parking lot from the system.
 * Sent when an edge server goes offline or a parking lot is permanently closed.
 */
public class DeregisterParkMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    private final String parkId;

    public DeregisterParkMessage(String parkId) {
        this.parkId = parkId;
    }

    public String getParkId() {
        return parkId;
    }

    @Override
    public String toString() {
        return "DeregisterParkMessage{" +
                "parkId='" + parkId + '\'' +
                '}';
    }
}

