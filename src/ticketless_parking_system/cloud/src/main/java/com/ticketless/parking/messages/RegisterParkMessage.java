package com.ticketless.parking.messages;

/**
 * Message to register a new parking lot with the parking lot manager.
 * This is sent by edge servers to dynamically create/register parking lots.
 */
public class RegisterParkMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    private final String parkId;
    private final int maxCapacity;

    public RegisterParkMessage(String parkId, int maxCapacity) {
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
        return "RegisterParkMessage{" +
                "parkId='" + parkId + '\'' +
                ", maxCapacity=" + maxCapacity +
                '}';
    }
}
