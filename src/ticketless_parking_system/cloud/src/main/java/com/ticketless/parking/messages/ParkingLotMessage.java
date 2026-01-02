package com.ticketless.parking.messages;

import java.io.Serializable;

/**
 * Base class for ParkingLot actor messages.
 * All messages must be immutable and serializable for actor communication.
 */
public abstract class ParkingLotMessage implements Serializable {
    private static final long serialVersionUID = 1L;
}
