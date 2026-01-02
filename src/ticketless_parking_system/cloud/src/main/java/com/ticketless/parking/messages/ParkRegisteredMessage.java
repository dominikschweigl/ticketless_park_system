package com.ticketless.parking.messages;

import akka.actor.ActorRef;

/**
 * Confirmation message sent when a parking lot is successfully registered.
 * Includes a reference to the newly created ParkingLotActor.
 */
public class ParkRegisteredMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    private final String parkId;
    private final int maxCapacity;
    private final transient ActorRef parkActorRef;

    public ParkRegisteredMessage(String parkId, int maxCapacity, ActorRef parkActorRef) {
        this.parkId = parkId;
        this.maxCapacity = maxCapacity;
        this.parkActorRef = parkActorRef;
    }

    public String getParkId() {
        return parkId;
    }

    public int getMaxCapacity() {
        return maxCapacity;
    }

    public ActorRef getParkActorRef() {
        return parkActorRef;
    }

    @Override
    public String toString() {
        return "ParkRegisteredMessage{" +
                "parkId='" + parkId + '\'' +
                ", maxCapacity=" + maxCapacity +
                ", parkActorRef=" + parkActorRef +
                '}';
    }
}
