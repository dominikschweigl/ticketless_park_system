package com.ticketless.parking.messages;

/**
 * Message to request the current status of a parking lot.
 */
public class GetStatusMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    public static final GetStatusMessage INSTANCE = new GetStatusMessage();

    private GetStatusMessage() {
    }

    @Override
    public String toString() {
        return "GetStatusMessage{}";
    }
}
