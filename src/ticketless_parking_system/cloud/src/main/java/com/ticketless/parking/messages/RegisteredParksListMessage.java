package com.ticketless.parking.messages;

import java.util.HashMap;
import java.util.Map;

/**
 * Message containing a list of all registered parking lots.
 * Maps parkId to maxCapacity.
 */
public class RegisteredParksListMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    private final Map<String, Integer> parks;

    public RegisteredParksListMessage(Map<String, Integer> parks) {
        this.parks = new HashMap<>(parks);
    }

    public Map<String, Integer> getParks() {
        return new HashMap<>(parks);
    }

    @Override
    public String toString() {
        return "RegisteredParksListMessage{" +
                "parks=" + parks +
                '}';
    }
}
