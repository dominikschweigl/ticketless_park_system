package com.ticketless.parking.actors;

import akka.actor.AbstractActor;
import akka.actor.ActorRef;
import akka.actor.Props;
import akka.event.Logging;
import akka.event.LoggingAdapter;
import com.ticketless.parking.messages.*;

import java.util.HashMap;
import java.util.Map;

/**
 * ParkingLotManagerActor supervises all ParkingLotActors.
 * 
 * Responsibilities:
 * - Register new parking lots dynamically (from edge servers)
 * - Maintain registry of all active parking lots
 * - Route occupancy messages to appropriate ParkingLotActors
 * - Provide list of registered parks
 * 
 * This allows edge servers to:
 * 1. Discover existing parking lots via GetRegisteredParksMessage
 * 2. Create new parking lots via RegisterParkMessage
 * 3. Send occupancy updates to specific parking lots via OccupancyMessage
 */
public class ParkingLotManagerActor extends AbstractActor {
    private final LoggingAdapter log = Logging.getLogger(getContext().getSystem(), this);

    // Map of parkId -> ParkingLotActor reference
    private final Map<String, ActorRef> parkActors = new HashMap<>();
    // Map of parkId -> max capacity
    private final Map<String, Integer> parkCapacities = new HashMap<>();

    public static Props props() {
        return Props.create(ParkingLotManagerActor.class);
    }

    @Override
    public void preStart() throws Exception {
        super.preStart();
        log.info("ParkingLotManagerActor started");
    }

    @Override
    public Receive createReceive() {
        return receiveBuilder()
                .match(RegisterParkMessage.class, this::handleRegisterPark)
                .match(GetRegisteredParksMessage.class, this::handleGetRegisteredParks)
                .match(ParkingLotOccupancyMessage.class, this::handleOccupancyUpdate)
                .match(GetParkingLotStatusMessage.class, this::handleGetStatus)
                .matchAny(this::unhandled)
                .build();
    }

    /**
     * Handles registration of a new parking lot.
     * Creates a new ParkingLotActor if it doesn't already exist.
     */
    private void handleRegisterPark(RegisterParkMessage message) {
        String parkId = message.getParkId();

        if (parkActors.containsKey(parkId)) {
            log.warning("Parking lot {} already registered", parkId);
            sender().tell(new ParkRegisteredMessage(parkId, parkCapacities.get(parkId), parkActors.get(parkId)), self());
            return;
        }

        // Create new ParkingLotActor
        ActorRef parkActor = getContext().actorOf(
                ParkingLotActor.props(parkId, message.getMaxCapacity()),
                "park-" + parkId
        );

        parkActors.put(parkId, parkActor);
        parkCapacities.put(parkId, message.getMaxCapacity());

        log.info("Registered parking lot {} (capacity: {})",
                parkId, message.getMaxCapacity());

        // Send confirmation back to the edge server
        sender().tell(new ParkRegisteredMessage(parkId, message.getMaxCapacity(), parkActor), self());
    }

    /**
     * Handles request for list of registered parking lots.
     * Edge servers use this to discover existing parking lots.
     */
    private void handleGetRegisteredParks(GetRegisteredParksMessage message) {
        RegisteredParksListMessage response = new RegisteredParksListMessage(parkCapacities);
        log.debug("Returning list of {} registered parks", parkCapacities.size());
        sender().tell(response, self());
    }

    /**
     * Routes occupancy update messages to the appropriate parking lot.
     * Edge servers send this with the current occupancy count.
     */
    private void handleOccupancyUpdate(ParkingLotOccupancyMessage message) {
        String parkId = message.getParkId();
        ActorRef parkActor = parkActors.get(parkId);
        if (parkActor != null) {
            parkActor.tell(message, sender());
        } else {
            log.warning("Parking lot {} not found for occupancy update", parkId);
        }
    }

    /**
     * Routes status queries to the appropriate parking lot.
     */
    private void handleGetStatus(GetParkingLotStatusMessage message) {
        String parkId = message.getParkId();
        ActorRef parkActor = parkActors.get(parkId);

        if (parkActor != null) {
            parkActor.forward(message, getContext());
        } else {
            log.warning("Parking lot {} not found for status query", parkId);
            sender().tell(new ParkingLotStatusMessage(parkId, 0, 0, false), self());
        }
    }

    @Override
    public void unhandled(Object message) {
        log.warning("Received unhandled message: {}", message);
        super.unhandled(message);
    }
}
