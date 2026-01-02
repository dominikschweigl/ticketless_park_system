package com.ticketless.parking.messages;

/**
 * Message containing the current status of a parking lot.
 */
public class ParkingLotStatusMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    private final String parkId;
    private final int currentOccupancy;
    private final int maxCapacity;
    private final boolean isFull;

    public ParkingLotStatusMessage(String parkId, int currentOccupancy, int maxCapacity, boolean isFull) {
        this.parkId = parkId;
        this.currentOccupancy = currentOccupancy;
        this.maxCapacity = maxCapacity;
        this.isFull = isFull;
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

    public boolean isFull() {
        return isFull;
    }

    @Override
    public String toString() {
        return "ParkingLotStatusMessage{" +
                "parkId='" + parkId + '\'' +
                ", currentOccupancy=" + currentOccupancy +
                ", maxCapacity=" + maxCapacity +
                ", isFull=" + isFull +
                '}';
    }
}
