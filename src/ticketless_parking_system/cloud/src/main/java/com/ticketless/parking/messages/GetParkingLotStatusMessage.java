package com.ticketless.parking.messages;

/**
 * Message to request the current status of a parking lot.
 */
public class GetParkingLotStatusMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    @Override
    public String toString() {
        return "GetStatusMessage{}";
    }
}
