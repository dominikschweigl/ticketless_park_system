package com.ticketless.parking.messages;

/**
 * Message sent by edge servers with the current occupancy of a parking lot.
 * This is the source of truth for parking lot state—the edge server measures
 * actual occupancy via sensors and periodically reports it.
 * 
 * This replaces the individual CarArrivedMessage/CarDepartedMessage pattern
 * with a simpler occupancy-based approach.
 */
public class OccupancyMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    private final String parkId;
    private final int currentOccupancy;
    private final long timestamp;
    private final String edgeServerId;

    /**
     * Creates an occupancy message.
     *
     * @param parkId           Unique identifier for the parking lot
     * @param currentOccupancy Number of cars currently in the lot
     * @param timestamp        When this measurement was taken (edge server time)
     * @param edgeServerId     Identifier of the edge server sending this
     */
    public OccupancyMessage(String parkId, int currentOccupancy, long timestamp, String edgeServerId) {
        this.parkId = parkId;
        this.currentOccupancy = currentOccupancy;
        this.timestamp = timestamp;
        this.edgeServerId = edgeServerId;
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

    public String getEdgeServerId() {
        return edgeServerId;
    }

    @Override
    public String toString() {
        return "OccupancyMessage{" +
                "parkId='" + parkId + '\'' +
                ", currentOccupancy=" + currentOccupancy +
                ", timestamp=" + timestamp +
                ", edgeServerId='" + edgeServerId + '\'' +
                '}';
    }
}
