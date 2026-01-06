package com.ticketless.parking.messages;

/**
 * Message to request the current status of a parking lot.
 */
public class GetParkingLotStatusMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    private final String parkId;

    public GetParkingLotStatusMessage(String parkId) {
        this.parkId = parkId;
    }

    public String getParkId() {
        return parkId;
    }

    @Override
    public String toString() {
        return "GetParkingLotStatusMessage{parkId='" + parkId + "'}";
    }
}
