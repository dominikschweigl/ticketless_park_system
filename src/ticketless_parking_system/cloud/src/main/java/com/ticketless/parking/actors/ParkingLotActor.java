package com.ticketless.parking.actors;

import akka.actor.AbstractActor;
import akka.actor.Props;
import akka.event.Logging;
import akka.event.LoggingAdapter;
import com.ticketless.parking.messages.*;

/**
 * ParkingLotActor manages a single parking lot.
 * Each parking lot has an actor instance that tracks:
 * - Current occupancy (number of cars)
 * - Maximum capacity
 * - Last update timestamp
 * 
 * Messages handled:
 * - OccupancyMessage: Periodic occupancy update from edge server
 * - GetStatusMessage: Request current parking lot status
 * 
 * State Management:
 * - Receives occupancy updates from edge servers (which measure via sensors)
 * - Edge server is the source of truth; cloud mirrors the state
 * - No need for periodic state broadcasts; edge server controls update frequency
 */
public class ParkingLotActor extends AbstractActor {
    private final LoggingAdapter log = Logging.getLogger(getContext().getSystem(), this);

    private final String parkId;
    private final int maxCapacity;
    private int currentOccupancy;
    private long lastUpdateTimestamp;
    private String lastEdgeServerId;

    /**
     * Creates a new ParkingLotActor instance.
     *
     * @param parkId      Unique identifier for this parking lot
     * @param maxCapacity Maximum number of cars allowed in this parking lot
     */
    public ParkingLotActor(String parkId, int maxCapacity) {
        this.parkId = parkId;
        this.maxCapacity = maxCapacity;
        this.currentOccupancy = 0;
        this.lastUpdateTimestamp = System.currentTimeMillis();
        this.lastEdgeServerId = "unknown";
        log.info("ParkingLotActor initialized for park {} with capacity {}", parkId, maxCapacity);
    }

    /**
     * Factory method to create Props for this actor.
     * Used with ActorSystem.actorOf(ParkingLotActor.props(...))
     */
    public static Props props(String parkId, int maxCapacity) {
        return Props.create(ParkingLotActor.class, parkId, maxCapacity);
    }

    @Override
    public void preStart() throws Exception {
        super.preStart();
        log.debug("ParkingLotActor started for park {}", parkId);
    }

    @Override
    public void postStop() throws Exception {
        super.postStop();
        log.info("ParkingLotActor stopped for park {}", parkId);
    }

    @Override
    public Receive createReceive() {
        return receiveBuilder()
                .match(ParkingLotOccupancyMessage.class, this::handleOccupancyUpdate)
                .match(GetParkingLotStatusMessage.class, this::handleGetStatus)
                .matchAny(this::unhandled)
                .build();
    }

    /**
     * Handles occupancy update from edge server.
     * Edge servers send this periodically with the current number of cars.
     */
    private void handleOccupancyUpdate(ParkingLotOccupancyMessage message) {
        currentOccupancy = message.getCurrentOccupancy();
        lastUpdateTimestamp = message.getTimestamp();
        lastEdgeServerId = message.getEdgeServerId();

        // Validate occupancy doesn't exceed capacity
        if (currentOccupancy > maxCapacity) {
            log.warning("Occupancy {} exceeds capacity {} for park {}. " +
                    "This may indicate a sensor error at edge server {}",
                    currentOccupancy, maxCapacity, parkId, lastEdgeServerId);
        }

        log.info("Occupancy update for park {}: {}/{} cars (from edge server {})",
                parkId, currentOccupancy, maxCapacity, lastEdgeServerId);
    }

    /**
     * Handles a status query.
     * Returns a ParkingLotStatusMessage with the current state.
     */
    private void handleGetStatus(GetParkingLotStatusMessage message) {
        boolean isFull = currentOccupancy >= maxCapacity;
        ParkingLotStatusMessage response = new ParkingLotStatusMessage(
                parkId,
                currentOccupancy,
                maxCapacity,
                isFull
        );
        log.debug("Status requested for park {}. Responding with: {}", parkId, response);
        sender().tell(response, self());
    }

    @Override
    public void unhandled(Object message) {
        log.warning("Received unhandled message: {}", message);
        super.unhandled(message);
    }
}
