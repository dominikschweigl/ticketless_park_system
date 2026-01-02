package com.ticketless.parking.messages;

/**
 * Periodic state update message sent by ParkingLotActor.
 * This ensures state is synchronized even if individual arrival/departure messages are lost.
 * Sent at regular intervals (e.g., every 5-10 seconds).
 */
public class ParkingLotStateUpdateMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    private final String parkId;
    private final int currentOccupancy;
    private final int maxCapacity;
    private final long timestamp;

    public ParkingLotStateUpdateMessage(String parkId, int currentOccupancy, int maxCapacity, long timestamp) {
        this.parkId = parkId;
        this.currentOccupancy = currentOccupancy;
        this.maxCapacity = maxCapacity;
        this.timestamp = timestamp;
    }

    public String getParkId() {
        return parkId;
    }

    public int getCurrentOccupancy() {
        return currentOccupancy;
    }

    public int getMaxCapacity() {
        return maxCapacity;
    }

    public long getTimestamp() {
        return timestamp;
    }

    @Override
    public String toString() {
        return "ParkingLotStateUpdateMessage{" +
                "parkId='" + parkId + '\'' +
                ", currentOccupancy=" + currentOccupancy +
                ", maxCapacity=" + maxCapacity +
                ", timestamp=" + timestamp +
                '}';
    }
}

