package com.ticketless.parking.messages;

/**
 * Confirmation message sent when a parking lot has been successfully deregistered.
 */
public class ParkDeregisteredMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    private final String parkId;

    public ParkDeregisteredMessage(String parkId) {
        this.parkId = parkId;
    }

    public String getParkId() {
        return parkId;
    }

    @Override
    public String toString() {
        return "ParkDeregisteredMessage{" +
                "parkId='" + parkId + '\'' +
                '}';
    }
}

