package com.ticketless.parking.actors;

import akka.actor.typed.Behavior;
import akka.actor.typed.ActorRef;
import akka.actor.typed.javadsl.Behaviors;
import akka.actor.typed.javadsl.ActorContext;
import akka.actor.typed.javadsl.Receive;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.ticketless.parking.messages.*;

import java.util.HashMap;
import java.util.Map;

/**
 * Akka Typed ParkingLotManagerActor supervises all ParkingLotActors.
 */
public class ParkingLotManagerActor {

    // Protocol
    public interface Command {}

    public static final class RegisterLot implements Command {
        public final String parkId;
        public final int maxCapacity;
        public final ActorRef<ParkRegisteredMessage> replyTo;
        public RegisterLot(String parkId, int maxCapacity, ActorRef<ParkRegisteredMessage> replyTo) {
            this.parkId = parkId;
            this.maxCapacity = maxCapacity;
            this.replyTo = replyTo;
        }
    }

    public static final class RegisterLotNoReply implements Command {
        public final String parkId;
        public final int maxCapacity;
        public RegisterLotNoReply(String parkId, int maxCapacity) {
            this.parkId = parkId;
            this.maxCapacity = maxCapacity;
        }
    }

    public static final class DeregisterLot implements Command {
        public final String parkId;
        public final ActorRef<ParkDeregisteredMessage> replyTo;
        public DeregisterLot(String parkId, ActorRef<ParkDeregisteredMessage> replyTo) {
            this.parkId = parkId;
            this.replyTo = replyTo;
        }
    }

    public static final class UpdateOccupancy implements Command {
        public final String parkId;
        public final int currentOccupancy;
        public final long timestamp;
        public UpdateOccupancy(String parkId, int currentOccupancy, long timestamp) {
            this.parkId = parkId;
            this.currentOccupancy = currentOccupancy;
            this.timestamp = timestamp;
        }
    }

    public static final class GetStatus implements Command {
        public final String parkId;
        public final ActorRef<ParkingLotStatusMessage> replyTo;
        public GetStatus(String parkId, ActorRef<ParkingLotStatusMessage> replyTo) {
            this.parkId = parkId;
            this.replyTo = replyTo;
        }
    }

    public static final class GetRegistered implements Command {
        public final ActorRef<RegisteredParksListMessage> replyTo;
        public GetRegistered(ActorRef<RegisteredParksListMessage> replyTo) {
            this.replyTo = replyTo;
        }
    }

    // Factory
    public static Behavior<Command> create() {
        return Behaviors.setup(ctx -> new ManagerBehavior(ctx).behavior());
    }

    // Internal behavior implementation
    private static class ManagerBehavior {
        private final ActorContext<Command> ctx;
        private final Logger log = LoggerFactory.getLogger(ParkingLotManagerActor.class);
        private final Map<String, ActorRef<ParkingLotActor.Command>> parkActors = new HashMap<>();
        private final Map<String, Integer> parkCapacities = new HashMap<>();

        ManagerBehavior(ActorContext<Command> ctx) {
            this.ctx = ctx;
            log.info("ParkingLotManagerActor started");
        }

        Behavior<Command> behavior() {
            return Behaviors.receive(Command.class)
                    .onMessage(RegisterLot.class, this::onRegisterLot)
                    .onMessage(RegisterLotNoReply.class, this::onRegisterLotNoReply)
                    .onMessage(DeregisterLot.class, this::onDeregisterLot)
                    .onMessage(UpdateOccupancy.class, this::onUpdateOccupancy)
                    .onMessage(GetStatus.class, this::onGetStatus)
                    .onMessage(GetRegistered.class, this::onGetRegistered)
                    .build();
        }

        private Behavior<Command> onRegisterLot(RegisterLot msg) {
            String parkId = msg.parkId;
            if (parkActors.containsKey(parkId)) {
                log.warn("Parking lot {} already registered", parkId);
                msg.replyTo.tell(new ParkRegisteredMessage(parkId, parkCapacities.get(parkId)));
                return Behaviors.same();
            }
            ActorRef<ParkingLotActor.Command> child = ctx.spawn(ParkingLotActor.create(parkId, msg.maxCapacity), "park-" + parkId);
            parkActors.put(parkId, child);
            parkCapacities.put(parkId, msg.maxCapacity);
            log.info("Registered parking lot {} (capacity: {})", parkId, msg.maxCapacity);
            msg.replyTo.tell(new ParkRegisteredMessage(parkId, msg.maxCapacity));
            return Behaviors.same();
        }

        private Behavior<Command> onRegisterLotNoReply(RegisterLotNoReply msg) {
            String parkId = msg.parkId;
            if (parkActors.containsKey(parkId)) {
                log.warn("Parking lot {} already registered", parkId);
                return Behaviors.same();
            }
            ActorRef<ParkingLotActor.Command> child = ctx.spawn(ParkingLotActor.create(parkId, msg.maxCapacity), "park-" + parkId);
            parkActors.put(parkId, child);
            parkCapacities.put(parkId, msg.maxCapacity);
            log.info("Registered parking lot {} (capacity: {})", parkId, msg.maxCapacity);
            return Behaviors.same();
        }

        private Behavior<Command> onDeregisterLot(DeregisterLot msg) {
            String parkId = msg.parkId;
            ActorRef<ParkingLotActor.Command> child = parkActors.remove(parkId);
            if (child == null) {
                log.warn("Cannot deregister parking lot {} - not found", parkId);
                msg.replyTo.tell(new ParkDeregisteredMessage(parkId));
                return Behaviors.same();
            }
            parkCapacities.remove(parkId);
            ctx.stop(child);
            log.info("Deregistered parking lot {}", parkId);
            msg.replyTo.tell(new ParkDeregisteredMessage(parkId));
            return Behaviors.same();
        }

        private Behavior<Command> onUpdateOccupancy(UpdateOccupancy msg) {
            ActorRef<ParkingLotActor.Command> child = parkActors.get(msg.parkId);
            if (child != null) {
                child.tell(new ParkingLotActor.UpdateOccupancy(msg.currentOccupancy, msg.timestamp));
            } else {
                log.warn("Parking lot {} not found for occupancy update", msg.parkId);
            }
            return Behaviors.same();
        }

        private Behavior<Command> onGetStatus(GetStatus msg) {
            ActorRef<ParkingLotActor.Command> child = parkActors.get(msg.parkId);
            if (child != null) {
                child.tell(new ParkingLotActor.GetStatus(msg.replyTo));
            } else {
                log.warn("Parking lot {} not found for status query", msg.parkId);
                msg.replyTo.tell(new ParkingLotStatusMessage(msg.parkId, 0, 0, false));
            }
            return Behaviors.same();
        }

        private Behavior<Command> onGetRegistered(GetRegistered msg) {
            msg.replyTo.tell(new RegisteredParksListMessage(parkCapacities));
            return Behaviors.same();
        }
    }
}
