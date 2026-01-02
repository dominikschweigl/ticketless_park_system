package com.ticketless.parking.messages;

/**
 * Message to register a new parking lot with the parking lot manager.
 * This is sent by edge servers to dynamically create/register parking lots.
 */
public class RegisterParkMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    private final String parkId;
    private final int maxCapacity;
    private final String edgeServerId;

    public RegisterParkMessage(String parkId, int maxCapacity, String edgeServerId) {
        this.parkId = parkId;
        this.maxCapacity = maxCapacity;
        this.edgeServerId = edgeServerId;
    }

    public String getParkId() {
        return parkId;
    }

    public int getMaxCapacity() {
        return maxCapacity;
    }

    public String getEdgeServerId() {
        return edgeServerId;
    }

    @Override
    public String toString() {
        return "RegisterParkMessage{" +
                "parkId='" + parkId + '\'' +
                ", maxCapacity=" + maxCapacity +
                ", edgeServerId='" + edgeServerId + '\'' +
                '}';
    }
}
