package com.ticketless.parking.messages;

/**
 * Message to request a list of all registered parking lots.
 * Used by edge servers to discover existing parking lots.
 */
public class GetRegisteredParksMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    public static final GetRegisteredParksMessage INSTANCE = new GetRegisteredParksMessage();

    private GetRegisteredParksMessage() {
    }

    @Override
    public String toString() {
        return "GetRegisteredParksMessage{}";
    }
}
