package com.ticketless.parking.actors;

import akka.actor.typed.Behavior;
import akka.actor.typed.javadsl.Behaviors;
import akka.actor.typed.javadsl.ActorContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.ticketless.parking.messages.ParkingLotStatusMessage;

/**
 * Akka Typed ParkingLotActor that manages a single parking lot state.
 */
public class ParkingLotActor {

    // Protocol
    public interface Command {}

    public static final class UpdateOccupancy implements Command {
        public final int currentOccupancy;
        public final long timestamp;
        public UpdateOccupancy(int currentOccupancy, long timestamp) {
            this.currentOccupancy = currentOccupancy;
            this.timestamp = timestamp;
        }
    }

    public static final class GetStatus implements Command {
        public final akka.actor.typed.ActorRef<ParkingLotStatusMessage> replyTo;
        public GetStatus(akka.actor.typed.ActorRef<ParkingLotStatusMessage> replyTo) {
            this.replyTo = replyTo;
        }
    }

    // Factory
    public static Behavior<Command> create(String parkId, int maxCapacity, double lat, double lng) {
        return Behaviors.setup(ctx -> new ParkingLotBehavior(ctx, parkId, maxCapacity, lat, lng).behavior());
    }


    // Internal behavior implementation
    private static class ParkingLotBehavior {
        private final ActorContext<Command> ctx;
        private final Logger log = LoggerFactory.getLogger(ParkingLotActor.class);
        private final String parkId;
        private final int maxCapacity;
        private int currentOccupancy;
        private long lastUpdateTimestamp;
        private final double lat;
        private final double lng;

        ParkingLotBehavior(ActorContext<Command> ctx, String parkId, int maxCapacity, double lat, double lng) {
            this.ctx = ctx;
            this.parkId = parkId;
            this.maxCapacity = maxCapacity;
            this.currentOccupancy = 0;
            this.lastUpdateTimestamp = System.currentTimeMillis();
            this.lat = lat;
            this.lng = lng;
            log.info("ParkingLotActor initialized for park {} cap {} at ({}, {})", parkId, maxCapacity, lat, lng);
        }

        Behavior<Command> behavior() {
            return Behaviors.receive(Command.class)
                    .onMessage(UpdateOccupancy.class, this::onUpdateOccupancy)
                    .onMessage(GetStatus.class, this::onGetStatus)
                    .build();
        }

        private Behavior<Command> onUpdateOccupancy(UpdateOccupancy msg) {
            this.currentOccupancy = msg.currentOccupancy;
            this.lastUpdateTimestamp = msg.timestamp;
            if (currentOccupancy > maxCapacity) {
                log.warn("Occupancy {} exceeds capacity {} for park {}", currentOccupancy, maxCapacity, parkId);
            }
            log.info("Occupancy update for park {}: {}/{} cars", parkId, currentOccupancy, maxCapacity);
            return Behaviors.same();
        }

        private Behavior<Command> onGetStatus(GetStatus msg) {
            boolean isFull = currentOccupancy >= maxCapacity;
            ParkingLotStatusMessage response = new ParkingLotStatusMessage(
                    parkId,
                    currentOccupancy,
                    maxCapacity,
                    isFull,
                    lat,
                    lng
            );
            msg.replyTo.tell(response);
            return Behaviors.same();
        }
    }
}
