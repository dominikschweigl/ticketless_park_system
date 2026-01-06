package com.ticketless.parking.messages;

/**
 * Message sent by edge servers with the current occupancy of a parking lot.
 * This is the source of truth for parking lot state—the edge server measures
 * actual occupancy via sensors and periodically reports it.
 * 
 * This replaces the individual CarArrivedMessage/CarDepartedMessage pattern
 * with a simpler occupancy-based approach.
 */
public class ParkingLotOccupancyMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    private final String parkId;
    private final int currentOccupancy;
    private final long timestamp;

    /**
     * Creates an occupancy message.
     *
     * @param parkId           Unique identifier for the parking lot
     * @param currentOccupancy Number of cars currently in the lot
     * @param timestamp        When this measurement was taken (edge server time)
     */
    public ParkingLotOccupancyMessage(String parkId, int currentOccupancy, long timestamp) {
        this.parkId = parkId;
        this.currentOccupancy = currentOccupancy;
        this.timestamp = timestamp;
    }

    public String getParkId() {
        return parkId;
    }

    public int getCurrentOccupancy() {
        return currentOccupancy;
    }

    public long getTimestamp() {
        return timestamp;
    }

    @Override
    public String toString() {
        return "OccupancyMessage{" +
                "parkId='" + parkId + '\'' +
                ", currentOccupancy=" + currentOccupancy +
                ", timestamp=" + timestamp +
                '}';
    }
}
