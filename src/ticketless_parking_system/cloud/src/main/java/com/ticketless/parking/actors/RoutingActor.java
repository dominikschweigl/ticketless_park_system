package com.ticketless.parking.actors;

import akka.actor.typed.Behavior;
import akka.actor.typed.ActorRef;
import akka.actor.typed.Scheduler;
import akka.actor.typed.javadsl.Behaviors;
import akka.actor.typed.javadsl.ActorContext;
import akka.actor.typed.javadsl.AskPattern;
import com.ticketless.parking.messages.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionStage;
import java.util.stream.Collectors;
import java.util.stream.Stream;

/**
 * Actor responsible for routing and finding nearby parking lots.
 */
public class RoutingActor {
    private static final Logger logger = LoggerFactory.getLogger(RoutingActor.class);
    private static final Duration ASK_TIMEOUT = Duration.ofSeconds(5);

    public interface Command {}

    /**
     * Request to find nearby parking lots.
     */
    public static final class GetNearbyParkingLots implements Command {
        public final double userLat;
        public final double userLng;
        public final int limit;
        public final boolean onlyAvailable;
        public final ActorRef<NearbyParkingLotsResponseMessage> replyTo;

        public GetNearbyParkingLots(double userLat, double userLng, int limit, boolean onlyAvailable,
                                   ActorRef<NearbyParkingLotsResponseMessage> replyTo) {
            this.userLat = userLat;
            this.userLng = userLng;
            this.limit = limit;
            this.onlyAvailable = onlyAvailable;
            this.replyTo = replyTo;
        }
    }

    public static Behavior<Command> create(ActorRef<ParkingLotManagerActor.Command> parkingLotManager) {
        return Behaviors.setup(ctx -> new BehaviorImpl(ctx, parkingLotManager).behavior());
    }

    private static class BehaviorImpl {
        private final ActorContext<Command> ctx;
        private final ActorRef<ParkingLotManagerActor.Command> parkingLotManager;
        private final Scheduler scheduler;

        BehaviorImpl(ActorContext<Command> ctx, ActorRef<ParkingLotManagerActor.Command> parkingLotManager) {
            this.ctx = ctx;
            this.parkingLotManager = parkingLotManager;
            this.scheduler = ctx.getSystem().scheduler();
        }

        Behavior<Command> behavior() {
            return Behaviors.receive(Command.class)
                    .onMessage(GetNearbyParkingLots.class, this::onGetNearbyParkingLots)
                    .build();
        }

        private Behavior<Command> onGetNearbyParkingLots(GetNearbyParkingLots msg) {
            logger.debug("Finding nearby parking lots for location ({}, {})", msg.userLat, msg.userLng);

            // First, get all registered parking lots
            CompletionStage<RegisteredParksListMessage> regFut = AskPattern.ask(
                    parkingLotManager,
                    (ActorRef<RegisteredParksListMessage> replyTo) -> new ParkingLotManagerActor.GetRegistered(replyTo),
                    ASK_TIMEOUT,
                    scheduler
            );

            // Then, for each parking lot, get its status and calculate distance
            CompletionStage<NearbyParkingLotsResponseMessage> responseFut = regFut.thenCompose(reg -> {
                List<CompletableFuture<NearbyParkingLotsResponseMessage.NearbyLot>> futures = new ArrayList<>();

                for (String parkId : reg.getParks().keySet()) {
                    CompletionStage<ParkingLotStatusMessage> stStage = AskPattern.ask(
                            parkingLotManager,
                            (ActorRef<ParkingLotStatusMessage> replyTo) -> new ParkingLotManagerActor.GetStatus(parkId, replyTo),
                            ASK_TIMEOUT,
                            scheduler
                    );

                    CompletableFuture<NearbyParkingLotsResponseMessage.NearbyLot> lotF = stStage.thenApply(status -> {
                        double distM = haversineMeters(msg.userLat, msg.userLng, status.getLat(), status.getLng());
                        return new NearbyParkingLotsResponseMessage.NearbyLot(
                                status.getParkId(),
                                status.getLat(),
                                status.getLng(),
                                status.getMaxCapacity(),
                                status.getCurrentOccupancy(),
                                status.getAvailableSpaces(),
                                distM
                        );
                    }).toCompletableFuture();

                    futures.add(lotF);
                }

                return CompletableFuture
                        .allOf(futures.toArray(new CompletableFuture[0]))
                        .thenApply(v -> {
                            Stream<NearbyParkingLotsResponseMessage.NearbyLot> stream = futures.stream()
                                    .map(CompletableFuture::join);

                            if (msg.onlyAvailable) {
                                stream = stream.filter(l -> l.getAvailableSpaces() > 0);
                            }

                            List<NearbyParkingLotsResponseMessage.NearbyLot> results = stream
                                    .sorted(Comparator.comparingDouble(NearbyParkingLotsResponseMessage.NearbyLot::getDistanceMeters))
                                    .limit(msg.limit)
                                    .collect(Collectors.toList());

                            logger.debug("Found {} nearby parking lots", results.size());
                            return new NearbyParkingLotsResponseMessage(results);
                        });
            });

            // Send response back to the requester
            ctx.pipeToSelf(responseFut,
                    (response, throwable) -> {
                        if (throwable != null) {
                            logger.error("Error finding nearby parking lots", throwable);
                            // Send empty response on error
                            msg.replyTo.tell(new NearbyParkingLotsResponseMessage(new ArrayList<>()));
                        } else {
                            msg.replyTo.tell(response);
                        }
                        return null;
                    });

            return Behaviors.same();
        }

        /**
         * Calculate the haversine (great-circle) distance between two points in meters.
         */
        private static double haversineMeters(double lat1, double lon1, double lat2, double lon2) {
            final double R = 6371000.0; // Earth radius in meters
            double dLat = Math.toRadians(lat2 - lat1);
            double dLon = Math.toRadians(lon2 - lon1);

            double a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
                    + Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2))
                    * Math.sin(dLon / 2) * Math.sin(dLon / 2);

            double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
            return R * c;
        }
    }
}
