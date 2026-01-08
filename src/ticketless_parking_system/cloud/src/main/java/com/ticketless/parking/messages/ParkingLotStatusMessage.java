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
    private final double lat;
    private final double lng;

    public ParkingLotStatusMessage(String parkId, int currentOccupancy, int maxCapacity, boolean isFull, double lat, double lng) {
        this.parkId = parkId;
        this.currentOccupancy = currentOccupancy;
        this.maxCapacity = maxCapacity;
        this.isFull = isFull;
        this.lat = lat;
        this.lng = lng;
    }

    public String getParkId() {
        return parkId;
    }

    public int getCurrentOccupancy() {
        return currentOccupancy;
    }

    public double getLat() { 
        return lat; 
    }
    
    public double getLng() { 
        return lng; 
    }

    public int getMaxCapacity() {
        return maxCapacity;
    }

    public boolean isFull() {
        return isFull;
    }

    public int getAvailableSpaces() {
        return maxCapacity - currentOccupancy;
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
