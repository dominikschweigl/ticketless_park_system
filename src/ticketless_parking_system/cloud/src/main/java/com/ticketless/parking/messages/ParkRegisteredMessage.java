package com.ticketless.parking.messages;

/**
 * Confirmation message sent when a parking lot is successfully registered.
 */
public class ParkRegisteredMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    private final String parkId;
    private final int maxCapacity;

    public ParkRegisteredMessage(String parkId, int maxCapacity) {
        this.parkId = parkId;
        this.maxCapacity = maxCapacity;
    }

    public String getParkId() {
        return parkId;
    }

    public int getMaxCapacity() {
        return maxCapacity;
    }

    @Override
    public String toString() {
        return "ParkRegisteredMessage{" +
                "parkId='" + parkId + '\'' +
                ", maxCapacity=" + maxCapacity +
                '}';
    }
}
